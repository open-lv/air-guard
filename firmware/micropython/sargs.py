import logging
import mhz19
import mqtt
import network
import sargsui
import sys
import time
import uasyncio
from machine import Pin, I2C, UART, ADC
from umqtt.simple import MQTTException
from utils import *
from utime import ticks_ms

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

    wifi_ssid = None
    wifi_password = None

    # wifi housekeeping variables
    wifi_connection_time = None
    wifi_post_connection_tasks_run = False
    sta_if = network.WLAN(network.STA_IF)
    ap_if = network.WLAN(network.AP_IF)

    mqtt_client = None

    exit_requested = False

    def __init__(self):
        self.log = logging.getLogger("sargs")

    async def setup(self):
        self.ldr_adc.atten(ADC.ATTN_11DB)  # for some reason, specifying atten while creating ADC doesn't work

        self.log.info("Disabling WiFi interfaces")
        # disable WiFi interfaces
        self.ap_if.active(False)
        # disabling interface on startup helps with OSError Internal WiFi error when reconnecting
        self.sta_if.active(False)

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
        # I don't have the correct ESP32 module, and the module I'm using has UART2 pins connected to flash memory,
        # so I had to use UART1 -- this code will be removed once I get correct ESP32 module - RV
        from machine import unique_id
        if unique_id() == b"\xd8\xa0\x1d\x65\x27\x60":
            self.log.info("ESP32-D4 detected, using UART 1")
            self.co2_sensor_uart = 1

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
        self.screen.drawText(0, 20, "  CO2 sensors")
        self.screen.drawText(0, 30, "    neatbild!")
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
            self.wifi_ssid = config.WIFI_SSID
            self.wifi_password = config.WIFI_PASSWORD
            self.log.info("config imported")
        except ImportError:
            self.log.info("config does not exist, skipping")

    def handle_co2_measurement(self, m):
        self.co2_measurement = m
        if self.sta_if.isconnected() and self.mqtt_client:
            try:
                self.mqtt_client.handle_co2_measurement(m, self.co2_sensor.get_cached_temperature_reading())
            except (MQTTException, OSError) as e:
                self.log.error("error during mqtt publishing: %s" % repr(e))
                self.log.info("re-connecting to mqtt")
                self.connect_mqtt()

    def run_wifi(self):
        try:
            if self.wifi_ssid and not self.sta_if.active():
                self.log.info("enabling WiFi")
                self.sta_if.active(True)

            if self.wifi_ssid and not self.sta_if.isconnected() and (
                    self.wifi_connection_time is None
                    or (ticks_ms() - self.wifi_connection_time) > 5000
            ):
                self.wifi_connection_time = ticks_ms()
                self.wifi_post_connection_tasks_run = False
                self.log.info("connecting to WiFi AP: %s" % self.wifi_ssid)
                self.sta_if.connect(self.wifi_ssid, self.wifi_password)

            if self.sta_if.isconnected() and not self.wifi_post_connection_tasks_run:
                self.log.info("WiFi connected, ifconfig: %s" % str(self.sta_if.ifconfig()))
                self.connect_mqtt()
                self.wifi_post_connection_tasks_run = True

        except OSError as e:
            self.log.warning("OSError during wifi connection: %s" % e)
            self.sta_if.active(False)
            self.mqtt_client = None

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

        if self.sta_if.isconnected():
            wifi_state = sargsui.WiFiState.CONNECTED
        elif self.sta_if.active():
            wifi_state = sargsui.WiFiState.CONNECTING
        else:
            wifi_state = sargsui.WiFiState.UNCONFIGURED
        self.ui.set_wifi_state(wifi_state)

        await self.ui.update()

        if self.ui.calibration_requested:
            self.log.info("holding sensor calibration pin low")
            self.pin_co2_calibrate.value(0)
            await uasyncio.sleep(10)
            self.pin_co2_calibrate.value(1)
            self.ui.select_main_screen()

    async def run(self):
        """
        This task is executed in the context of a thread that's separate from main.py.
        It should handle re-drawing screen, handling WiFi status polling, 
        calibration statemachine (and probably something else I haven't thought about yet)
        """
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
                    self.run_wifi()
                    await uasyncio.sleep(0.03)
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
