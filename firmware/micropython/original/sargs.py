import binascii
import gc
import logging
import machine
import mhz19
import network
import http_utils
import ota_utils
from . import mqtt_airguard
from . import sargsui
from . import portal
import sys
import time
import uasyncio
import urequests
from machine import Pin, I2C, UART, ADC, reset
from uasyncio import CancelledError
from uasyncio import Task
from umqtt.simple import MQTTException
from .utils import *
from utime import ticks_ms
import network_manager
import config

logging.basicConfig(level=logging.INFO)

try:
    import display
except ImportError:
    l = logging.getLogger("sargs")
    l.error("cannot import display module. Most likely, you are running mainline micropython firmware")
    l.error("Please see https://github.com/open-lv/micropython")
    time.sleep(5)
    sys.exit(1)

HAND_BRIGHTNESS = 128
EYE_BRIGHTNESS = 128


class Sargs:
    sargs_instance = None

    UPDATE_CHECK_PERIOD = 1000 * 60 * 60  # once an hour
    INTERNET_CONNECTION_TIMEOUT = 10

    led_red = LEDPWMSignal(Pin(33, Pin.OUT), on_duty=HAND_BRIGHTNESS)
    led_yellow = LEDPWMSignal(Pin(25, Pin.OUT), on_duty=HAND_BRIGHTNESS)
    led_green = LEDPWMSignal(Pin(26, Pin.OUT), on_duty=HAND_BRIGHTNESS)
    led_left_eye = LEDPWMSignal(Pin(23, Pin.OUT), on_duty=EYE_BRIGHTNESS)
    led_right_eye = LEDPWMSignal(Pin(19, Pin.OUT), on_duty=EYE_BRIGHTNESS)

    btn_arm = Signal(Pin(35, Pin.IN, Pin.PULL_UP), invert=True)

    ldr_adc = ADC(Pin(34))
    pin_lcd_data = Pin(21, pull=Pin.PULL_UP)
    pin_lcd_clock = Pin(22, pull=Pin.PULL_UP)
    pin_co2_calibrate = Pin(27, Pin.OUT, value=1)

    co2_sensor_uart = 2
    co2_sensor = None
    buzzer = Buzzer(Pin(32))
    screen = None
    ui = None
    co2_measurement = None
    user_main_loop_started = False

    network_manager = None
    _internet_checker_task: uasyncio.Task = None
    _sta_if = network.WLAN(network.STA_IF)
    _ap_if = network.WLAN(network.AP_IF)

    mqtt_client = None

    exit_requested = False

    version = "XXX"

    machine_id = binascii.hexlify(machine.unique_id()).decode("ascii")
    machine_id_short = machine_id[:6]

    config = config.sargsConfig

    def __init__(self):
        self.log = logging.getLogger("sargs")

        # flash.sh/release process stores version in airguardversion.py file
        try:
            from . import airguardversion
            self.version = airguardversion.VERSION
            if self.version.startswith('micropython-'):
                self.version = self.version[12:]
            self.latest_version = self.version
            self.log.info("Airguard version: %s" % self.version)
        except ImportError:
            pass

    async def setup(self):
        self.ldr_adc.atten(ADC.ATTN_11DB)  # for some reason, specifying atten while creating ADC doesn't work

        # initialize hardware
        self.log.info("Initializing hardware")
        await self._init_lcd()
        await self._init_co2_sensor()

    async def _init_lcd(self):
        # initializing screen can fail if it doesn't respond to I2C commands, blink red LED and reboot
        try:
            # since the migration to advanced framebuffer, the drawing functions fail silently if screen does not
            # respond to I2C commands
            # trying to read one byte from the LCD on startup does the trick
            bus = I2C(0, scl=self.pin_lcd_clock, sda=self.pin_lcd_data)
            bus.readfrom(0x3c, 1)
            del bus

            self.screen = display
            self.screen.drawFill(0)
            self.screen.flush()
            self.ui = sargsui.SargsUI(self.screen, self.btn_arm, self.buzzer,
                                      self.ldr_adc, self.led_left_eye, self.led_right_eye)

            self.log.info("LCD initialized")
        except OSError:
            await self.handle_lcd_fault()

    async def handle_lcd_fault(self):
        self.exit_requested = True
        self.log.error("could not initialize LCD")
        for _ in range(30):
            self.led_red.on()
            await uasyncio.sleep(0.5)
            self.led_red.off()
            await uasyncio.sleep(0.5)
        reset()

    async def _init_co2_sensor(self):
        # initializing sensor can also fail (not present, damaged)- try to verify and blink yellow led if failed
        mhz_initialized = False

        for _ in range(3):
            try:
                self.co2_sensor = mhz19.MHZ19(UART(self.co2_sensor_uart, 9600, timeout=1000))
                mhz_initialized = await self.co2_sensor.verify()
                if mhz_initialized:
                    break
            except mhz19.MHZ19Exception:
                self.log.debug("re-trying CO2 sensor initialization...")
                await uasyncio.sleep(0.5)

        if not mhz_initialized:
            await self.handle_co2_sensor_fault()
        else:
            # turn off ABC calibration, as it would be an optimistic assumption that classrooms reach 400ppm
            # in any given day
            await self.co2_sensor.set_abc_state(False)

    async def handle_co2_sensor_fault(self):
        self.exit_requested = True
        self.log.error("CO2 sensor not responding")
        self.screen.drawFill(0)
        await self.draw_centered_text(20, "CO2 sensors")
        await self.draw_centered_text(32, "neatbild!")
        self.screen.flush()
        self.led_red.off()
        self.led_green.off()
        for _ in range(30):
            self.led_yellow.on()
            await uasyncio.sleep(0.5)
            self.led_yellow.off()
            await uasyncio.sleep(0.5)
        reset()

    def handle_co2_measurement(self, m):
        self.co2_measurement = m
        if self.mqtt_client:
            try:
                payload = '{ "co2": %d, "temperature": %d, firmwareVersion: "%s" }' % (
                    self.co2_measurement, self.co2_sensor.get_cached_temperature_reading(), self.version)
                self.mqtt_client.send_telemetry(payload)
            except (MQTTException, OSError) as e:
                self.log.error("error during mqtt publishing: %s" % repr(e))
                self.log.info("re-connecting to mqtt")
                self.connect_mqtt()

    def update_wifi_settings(self, wifi_ssid, wifi_password):
        self.config.WIFI_SSID = wifi_ssid
        self.config.WIFI_PASSWORD = wifi_password

        self.config.save()

        self.log.info("WiFi settings saved, restarting...")
        machine.reset()

    def connect_mqtt(self):
        """" Tries to initialize mqtt connection if configured to do so. Should be called after wifi is connected """
        try:
            if not mqtt_airguard.AirGuardIotMQTTClient:
                self.log.error("MQTT connection class AirGuardIotMQTTClient not implemented")
            else:
                # TODO: Enable this only if users opt-in.
                self.mqtt_client = mqtt_airguard.AirGuardIotMQTTClient(self.machine_id, self.machine_id)
                self.log.info("mqtt initialized")

        except ImportError:
            self.log.info("mqtt requires valid configuration")

    async def run_screen(self):
        # update screen state
        if self.co2_measurement:
            self.ui.set_co2_measurement(self.co2_measurement)
            self.ui.set_temperature_measurement(self.co2_sensor.get_cached_temperature_reading())
            if self.led_red.value():
                level = sargsui.CO2Level.HIGH
            elif self.led_yellow.value():
                level = sargsui.CO2Level.MEDIUM
            else:
                level = sargsui.CO2Level.LOW
            self.ui.set_co2_level(level)

        await self.ui.update()

        if self.ui.calibration_requested:
            self.log.info("holding sensor calibration pin low")
            self.pin_co2_calibrate.value(0)
            await uasyncio.sleep(10)
            self.pin_co2_calibrate.value(1)
            self.ui.select_main_screen()

        if self.ui.ota_update_requested:
            self.log.info("starting ota...")
            self.update_to_latest_version()


    async def draw_centered_text(self, y, text):
        """Draws a horizontally centered line of text at specified offset from top"""
        x = (self.screen.width() - self.screen.getTextWidth(text)) // 2
        self.screen.drawText(x, y, text)

    def get_connected_ssid(self):
        return self._sta_if.config('essid')

    def get_wifi_ap_list(self):
        interface_state = self._sta_if.active()
        self._sta_if.active(True)
        stations = self._sta_if.scan()
        if not interface_state:
            self._sta_if.active(False)

        return stations

    def update_to_latest_version(self):
        if self.latest_version == self.version:
            self.log.error("Already at latest version: %s" % self.version)
            return

        self.prepare_ota(self.latest_version)

    def prepare_ota(self, version_name):
        self.log.info("Written new main.py for OTA")
        with open("main.py") as f:
            f.write("""

import ota
ota = ota.OTA()
ota.perform_update("%s")

""" % version_name)

        self.log.info("OTA information saved, restarting...")
        machine.reset()

    async def get_latest_version(self):
        reader = None
        try:
            # this method is blocking due to usocket.getaddrinfo
            # that resolved DNS name
            reader = http_utils.open_url("https://gaisasargs.lv/latest_release")
            await uasyncio.sleep_ms(0)
            line = reader.read(24).splitlines()[0]
            reader.close()
            await uasyncio.sleep_ms(0)

            latest_version = line.decode('latin1').rstrip()

            if not latest_version.startswith("micropython-"):
                raise Exception("Invalid version response: %s" % latest_version)

            return latest_version[12:]
        except Exception as e:
            self.log.exc(e, "Error while checking \"https://gaisasargs.lv/latest_release\" update")
        finally:
            if reader:
                reader.close()

        return None

    async def _check_internet(self):
        self.log.info("Internet connectivity checker started")
        last_version_check_time = -self.UPDATE_CHECK_PERIOD

        while True:
            try:
                reader, writer = await uasyncio.wait_for(uasyncio.open_connection('1.1.1.1', 53),
                                                         self.INTERNET_CONNECTION_TIMEOUT)
                await writer.aclose()
                self.ui.internet_state = sargsui.InternetState.CONNECTED

                if (time.ticks_ms() - last_version_check_time) > self.UPDATE_CHECK_PERIOD:
                    last_version_check_time = time.ticks_ms()
                    latest_version = await self.get_latest_version()

                    if latest_version:
                        update_available = latest_version != self.version

                        self.ui.update_available = update_available
                        self.ui.latest_version = latest_version
                        self.latest_version = latest_version
                        last_version_check_time = time.ticks_ms()

                        if update_available:
                            self.log.info("New update available!")
                            self.log.info(
                                "Current version: %s, latest version: %s" % (self.version, self.latest_version))
                    else:
                        self.log.info("Could not fetch update information")

                await uasyncio.sleep(30)
            except CancelledError:
                self.log.info("Internet connectivity checker cancelled")
                self.ui.internet_state = sargsui.InternetState.DISCONNECTED
                raise
            except Exception as e:
                self.log.info("error during internet connectivity check: %s. Retrying in 30 seconds" % repr(e))
                self.ui.internet_state = sargsui.InternetState.DISCONNECTED
                await uasyncio.sleep(30)

    def _on_network_manager_connected(self):
        self.ui.set_wifi_state(sargsui.WiFiState.CONNECTED)
        self.ui.set_display_ip_address(self._sta_if.ifconfig()[0])
        self.connect_mqtt()
        self._internet_checker_task = uasyncio.create_task(self._check_internet())

    def _on_network_manager_disconnected(self):
        self.ui.set_wifi_state(sargsui.WiFiState.DISCONNECTED)
        self.ui.set_display_ip_address(None)
        if self.mqtt_client:
            self.mqtt_client = None
        self._internet_checker_task.cancel()

    def _on_network_manager_connecting(self):
        self.ui.set_wifi_state(sargsui.WiFiState.CONNECTING)
        self.ui.set_display_ip_address(None)

    def _on_network_manager_ap_enabled(self):
        self.ui.set_wifi_state(sargsui.WiFiState.ACCESS_POINT)
        self.ui.set_display_ip_address(self._ap_if.ifconfig()[0])

    async def perform_co2_measurement(self):
        # @TODO: Handle repeated hecksum errors here
        if not self.user_main_loop_started:
            # on startup, wait for up to 120s for a valid reading
            self.user_main_loop_started = True
            heating_start_time = time.ticks_ms()
            while (time.ticks_ms() - heating_start_time) < 120 * 1000:
                if await self.co2_sensor.get_co2_reading() is not None:
                    break
                await uasyncio.sleep(1)

        # retry measurement up to three times, then give up and trigger error
        measurement = None
        for _ in range(3):
            measurement = await self.co2_sensor.get_co2_reading()
            if measurement is not None:
                break
            await uasyncio.sleep(1)

        if measurement is None:
            await self.handle_co2_sensor_fault()
        return measurement

    async def run(self):
        gc.collect()
        """
        This task is executed in the context of a thread that's separate from main.py.
        It should handle re-drawing screen, handling WiFi status polling, 
        calibration statemachine (and probably something else I haven't thought about yet)
        """
        if self.config.WIFI_ENABLED:
            if not self.config.WIFI_SSID and not self.config.CAPTIVE_PORTAL_ENABLED:
                self.log.warning("WIFI not enabled - no wifi configuration found and captive portal is disabled.")
            else:
                self.network_manager = network_manager.NetworkManager(self.config.WIFI_SSID,
                                                                      self.config.WIFI_PASSWORD,
                                                                      captive_portal_enabled=self.config.CAPTIVE_PORTAL_ENABLED,
                                                                      captive_portal_ssid="GaisaSargs-%s" % self.machine_id_short,
                                                                      on_connected=self._on_network_manager_connected,
                                                                      on_disconnected=self._on_network_manager_disconnected,
                                                                      on_ap_enabled=self._on_network_manager_ap_enabled,
                                                                      on_connecting=self._on_network_manager_connecting,
                                                                      )
                self.network_manager.start()

                portal.setup()
        else:
            self.log.warning("WIFI not enabled")

        self.log.info("starting background thread, waiting for user main thread to start")
        self.buzzer.duty(0)
        while not self.user_main_loop_started and not self.exit_requested:
            await uasyncio.sleep(0.1)
        self.log.info("background thread started")
        await self.buzzer.startup_beep()
        while not self.exit_requested:
            try:
                while not self.exit_requested:
                    await self.run_screen()
                    await uasyncio.sleep_ms(0)  # not more than 60FPS
            except KeyboardInterrupt as e:
                self.log.info("KeyboardInterrupt, exiting Sargs thread")
                self.exit_requested = True
                raise e
            except Exception as e:
                self.log.error("exception in main thread")
                self.log.error(e)
                sys.print_exception(e)
                self.log.info("re-starting main thread")


def setup():
    Sargs.sargs_instance = Sargs()
    return Sargs.sargs_instance
