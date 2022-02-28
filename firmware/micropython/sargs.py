import logging
import mhz19
import mqtt
import network
import sargsui
import sys
import time
import uasyncio
from machine import Pin, I2C, UART, ADC
from uasyncio import CancelledError
from uasyncio import Task
from umqtt.simple import MQTTException
from utils import *
from utime import ticks_ms
import network_manager

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

    _wifi_enabled = True
    _captive_portal_enabled = True
    _wifi_ssid = None
    _wifi_password = None

    network_manager = None
    _internet_checker_task: uasyncio.Task = None
    _sta_if = network.WLAN(network.STA_IF)
    _ap_if = network.WLAN(network.AP_IF)

    mqtt_client = None

    exit_requested = False

    version = "XXX"

    def __init__(self):
        self.log = logging.getLogger("sargs")

        # flash.sh/release process stores version in airguardversion.py file
        try:
            import airguardversion
            self.version = airguardversion.VERSION
        except ImportError:
            pass

    async def setup(self):
        self.ldr_adc.atten(ADC.ATTN_11DB)  # for some reason, specifying atten while creating ADC doesn't work

        # initialize hardware
        self.log.info("Initializing hardware")
        await self._init_lcd()
        await self._init_co2_sensor()

        # initialize configuration from config.py
        self.log.info("Initializing stored config")
        self._init_config()

    async def _init_lcd(self):
        # initializing screen can fail if it doesn't respond to I2C commands, blink red LED and reboot
        try:
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
        sys.exit()

    async def _init_co2_sensor(self):
        # initializing sensor can also fail (not present, damaged)- try to verify and blink yellow led if failed
        mhz_initialized = False

        for _ in range(3):
            try:
                self.co2_sensor = mhz19.MHZ19(UART(self.co2_sensor_uart, 9600, timeout=1000))
                mhz_initialized = self.co2_sensor.verify()
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
            self.co2_sensor.set_abc_state(False)

    async def handle_co2_sensor_fault(self):
        self.exit_requested = True
        self.log.error("CO2 sensor not responding")
        self.screen.drawFill(0)
        await self.draw_centered_text(20, "CO2 sensors")
        await self.draw_centered_text(32, "neatbild!")
        self.screen.flush()
        for _ in range(30):
            self.led_yellow.on()
            await uasyncio.sleep(0.5)
            self.led_yellow.off()
            await uasyncio.sleep(0.5)
        sys.exit()

    def _init_config(self):

        # config file can be non-existant
        try:
            import config
            self._wifi_enabled = config.WIFI_ENABLED
            self._captive_portal_enabled = config.CAPTIVE_PORTAL_ENABLED
            self._wifi_ssid = config.WIFI_SSID
            self._wifi_password = config.WIFI_PASSWORD
            self.log.info("config imported")
        except ImportError:
            self.log.info("config does not exist, skipping")

    def handle_co2_measurement(self, m):
        self.co2_measurement = m
        if self.mqtt_client:
            try:
                self.mqtt_client.handle_co2_measurement(m, self.co2_sensor.get_cached_temperature_reading())
            except (MQTTException, OSError) as e:
                self.log.error("error during mqtt publishing: %s" % repr(e))
                self.log.info("re-connecting to mqtt")
                self.connect_mqtt()

    def set_wifi_settings(self, wifi_ssid, wifi_password):
        if not self.network_manager:
            self.log.error("Trying to set WIFI settings without network manager")
            return

        self._wifi_ssid = wifi_ssid
        self._wifi_password = wifi_password
        self.network_manager.wifi_ssid = wifi_ssid
        self.network_manager.wifi_password = wifi_password
        self.network_manager.restart()

    def connect_mqtt(self):
        """" Tries to initialize mqtt connection if configured to do so. Should be called after wifi is connected """
        try:
            import config

            mqtt_class = getattr(mqtt, config.MQTT_CLASS, None)
            if not mqtt_class:
                self.log.error("MQTT connection class '%s' not implemented" % config.MQTT_CLASS)
            else:
                if getattr(config, "MQTT_CLIENT_ID", None):
                    self.mqtt_client = mqtt_class(config)
                    self.log.info("mqtt initialized")
                else:
                    self.log.error("missing mqtt client configuration")

        except ImportError:
            self.log.info("mqtt requires valid configuration")

    async def run_screen(self):
        # update screen state
        if self.co2_sensor.sensor_warmed_up:
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

    async def _check_internet(self):
        self.log.info("Internet connectivity checker started")

        while True:
            try:
                reader, writer = await uasyncio.wait_for(uasyncio.open_connection('1.1.1.1', 53),
                                                         self.INTERNET_CONNECTION_TIMEOUT)
                await writer.aclose()
                self.ui.internet_state = sargsui.InternetState.CONNECTED
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
        self.connect_mqtt()
        self._internet_checker_task = uasyncio.create_task(self._check_internet())

    def _on_network_manager_disconnected(self):
        self.ui.set_wifi_state(sargsui.WiFiState.DISCONNECTED)
        if self.mqtt_client:
            self.mqtt_client = None
        self._internet_checker_task.cancel()

    def _on_network_manager_connecting(self):
        self.ui.set_wifi_state(sargsui.WiFiState.CONNECTING)

    def _on_network_manager_ap_enabled(self):
        self.ui.set_wifi_state(sargsui.WiFiState.ACCESS_POINT)

    async def run(self):
        """
        This task is executed in the context of a thread that's separate from main.py.
        It should handle re-drawing screen, handling WiFi status polling, 
        calibration statemachine (and probably something else I haven't thought about yet)
        """
        if self._wifi_enabled:
            if not self._wifi_ssid and not self._captive_portal_enabled:
                self.log.warning("WIFI not enabled - no wifi configuration found and captive portal is disabled.")
            else:
                self.network_manager = network_manager.NetworkManager(self._wifi_ssid, self._wifi_password,
                                                                      captive_portal_enabled=self._captive_portal_enabled,
                                                                      captive_portal_ssid="GaisaSargs",
                                                                      on_connected=self._on_network_manager_connected,
                                                                      on_disconnected=self._on_network_manager_disconnected,
                                                                      on_ap_enabled=self._on_network_manager_ap_enabled,
                                                                      on_connecting=self._on_network_manager_connecting,
                                                                      )
                self.network_manager.start()
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
                    await uasyncio.sleep(0.01)
            except KeyboardInterrupt as e:
                self.log.info("KeyboardInterrupt, exiting Sargs thread")
                self.exit_requested = True
                raise e
            except Exception as e:
                self.log.error("exception in main thread")
                self.log.error(e)
                import sys
                sys.print_exception(e)
                self.log.info("re-starting main thread")


sargs = Sargs()


async def perform_co2_measurement():
    # @TODO: Handle repeated hecksum errors here
    sargs.user_main_loop_started = True
    heating_start_time = time.ticks_ms()
    measurement = None
    while (time.ticks_ms() - heating_start_time) < 120 * 1000:
        measurement = sargs.co2_sensor.get_co2_reading()
        if measurement is not None:
            return measurement
        await uasyncio.sleep(1)

    if measurement is None:
        await sargs.handle_co2_sensor_fault()
