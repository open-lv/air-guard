from machine import Pin, I2C, PWM, UART, Signal
import mhz19
import logging
import ssd1306
import network
from umqtt.simple import MQTTClient
from utime import sleep
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
    
    def __init__(self):
        self.pwm_buzzer.duty(0)
        self.log = logging.getLogger("sargs")

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
                
    def handle_co2_measurement(self, m):
        self.co2_measurement = m

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

            self.screen.show()
            
            # @TODO: initiate calibration based on button
            if self.btn_arm.value():
                self.led_right_eye.on()
                self.led_left_eye.on()
            else:
                self.led_right_eye.off()
                self.led_left_eye.off()
                
            sleep(0.1)

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
