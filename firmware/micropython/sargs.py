from machine import Pin, I2C, PWM, UART, Signal
import mhz19
import logging
import ssd1306
import network
from umqtt.simple import MQTTClient
from utime import sleep, ticks_ms
from utils import *
import _thread

class Sargs:
    
    led_red = LEDSignal(Pin(33, Pin.OUT))
    led_yellow = LEDSignal(Pin(25, Pin.OUT))
    led_green = LEDSignal(Pin(26, Pin.OUT))
    led_left_eye = LEDSignal(Pin(23, Pin.OUT))
    led_right_eye = LEDSignal(Pin(19, Pin.OUT))

    btn_arm = Signal(Pin(35, Pin.IN, Pin.PULL_UP), invert=True)
    
    pin_ldr = Pin(34, Pin.IN)
    pin_lcd_data = Pin(21, pull=Pin.PULL_UP)
    pin_lcd_clock = Pin(22, pull=Pin.PULL_UP)
    
    co2_sensor_uart = 2
    co2_sensor = None
    
    pwm_buzzer = PWM(Pin(32, Pin.OUT, value=0), freq=1000, duty=0)
    screen = None
    
    co2_measurement = None
    user_main_loop_started = False
    
    wifi_ssid = None
    wifi_password = None
    
    # wifi housekeeping variables
    wifi_connection_time = 0
    wifi_post_connection_tasks_run = False
    sta_if = network.WLAN(network.STA_IF)
    ap_if = network.WLAN(network.AP_IF)
    
    mqtt_client = None
    
    def __init__(self):
        self.pwm_buzzer.duty(0)
        self.log = logging.getLogger("sargs")
        
        # disable WiFi interfaces
        self.ap_if.active(False)
        # disabling interface on startup helps with OSError Internal WiFi error when reconnecting
        self.sta_if.active(False)
        
        # initialize hardware
        self._init_lcd()
        self._init_co2_sensor()
        
        # initialize configuration from config.py
        self._init_config()
        
    def _init_lcd(self):
        # initializing screen can fail if it doesn't respond to I2C commands, blink red LED and reboot
        try:
            self.screen = ssd1306.SSD1306_I2C(128, 64, I2C(0, sda=self.pin_lcd_data, scl=self.pin_lcd_clock))
            self.log.info("LCD initialized")
        except OSError:
            self.log.error("could not initialize LCD")
            for _ in range(30):
                self.led_red.turn_on()
                sleep(0.5)
                self.led_red.turn_off()
                sleep(0.5)
            sys.exit()
            
    def _init_co2_sensor(self):
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
                break
            except mhz19.MHZ19Exception:
                self.log.debug("re-trying CO2 sensor initialization...")
                sleep(0.5)
                
        if not mhz_initialized: 
            self.log.error("CO2 sensor not responding")
            self.screen.fill(0)
            self.screen.text("CO2 sensors neatbild", 0, 0, 1)
            self.screen.draw()
            for _ in range(30):
                self.led_yellow.turn_on()
                sleep(0.5)
                self.led_yellow.turn_off()
                sleep(0.5)
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

    def run_wifi(self):
        try:
            if self.wifi_ssid and not self.sta_if.active():
                self.log.info("enabling WiFi")
                self.sta_if.active(True)
            
            if self.wifi_ssid and not self.sta_if.isconnected() and (ticks_ms() - self.wifi_connection_time) > 5000:
                self.wifi_connection_time = ticks_ms()
                self.wifi_post_connection_tasks_run = False
                self.log.info("connecting to WiFi AP: %s" % self.wifi_ssid)
                self.sta_if.connect(self.wifi_ssid, self.wifi_password)
            
            if self.sta_if.isconnected() and not self.wifi_post_connection_tasks_run:
                self.log.info("WiFi connected, ifconfig: %s" % str(self.sta_if.ifconfig()))
                self.wifi_post_connection_tasks_run = True
        except OSError as e:
            self.log.warning("OSError during wifi connection: %s" % e)
            self.sta_if.active(False)
            
    def run_screen(self):
        self.screen.fill(0)

        if self.co2_measurement is None:
            self.screen.text("Sensors uzsilst", 0, 0, 1)
        else:
            self.screen.text("CO2: %d ppm" % self.co2_measurement, 0, 0, 1)


        # since user can change the threshold in main.py, use the state of output LEDs
        if self.led_green.value():
            self.screen.text("LABS GAISS!", 0, 20, 2)
        elif self.led_yellow.value():
            self.screen.text("ATVER LOGU!", 0, 20, 2)
        elif self.led_red.value():
            self.screen.text("AARGH!", 0, 20, 2)
        
       
        
        wifi_status_text = "WiFi: "
        if self.wifi_ssid:
            if self.sta_if.isconnected():
                wifi_status_text += "savienots"
            else:
                wifi_status_text += "savienojas"
        else:
            wifi_status_text += "nav konf."
            
        self.screen.text(wifi_status_text, 0, 30, 2)
        self.screen.show()
        
        
    def run_thread(self):
        """
        This task is executed in the context of a thread that's separate from main.py.
        It should handle re-drawing screen, handling WiFi status polling, 
        calibration statemachine (and probably something else I haven't thought about yet)
        """
        self.log.info("starting background thread, waiting for user main thread to start")
        while not self.user_main_loop_started:
            sleep(0.1)
        self.log.info("background thread started")
        
        
        while True:
            try:
                while True:
                    self.run_screen()
                    self.run_wifi()
                    
                    # @TODO: initiate calibration based on button
                    if self.btn_arm.value():
                        self.led_right_eye.on()
                        self.led_left_eye.on()
                    else:
                        self.led_right_eye.off()
                        self.led_left_eye.off()
                    
                    sleep(0.1)
            except Exception as e:
                self.log.error("exception in main thread")
                self.log.error(e)
                import sys
                sys.print_exception(e)
                self.log.info("re-starting main thread")

sargs = Sargs()

for a in ['led_red', 'led_green', 'led_yellow', 'led_right_eye', 'led_left_eye', 'screen', 'co2_sensor']:
    globals()[a.upper()] = getattr(sargs, a)

def perform_co2_measurement():
    #@TODO: Handle repeated hecksum errors here
    sargs.user_main_loop_started = True
    return sargs.co2_sensor.get_co2_reading()

def handle_co2_measurement(m):
    sargs.handle_co2_measurement(m)
    
_thread.start_new_thread(Sargs.run_thread, (sargs, ))
