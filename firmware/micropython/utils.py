from machine import Signal, PWM
from utime import sleep


class LEDSignal(Signal):

    def ieslegt(self):
        self.value(1)

    def izslegt(self):
        self.value(0)


class Buzzer(PWM):
    """Implements blocking methods for various beeps/tones"""
    def __init__(self, pin):
        super().__init__(pin)
        self.init(freq=1000, duty=0)

    def startup_beep(self):
        self.duty(512)
        sleep(0.5)
        self.duty(0)

    def short_beep(self):
        self.duty(512)
        sleep(0.1)
        self.duty(0)

    def long_beep(self):
        self.duty(512)
        sleep(0.7)
        self.duty(0)

    def high_co2_level_alert(self):
        for i in range(3):
            self.duty(512)
            sleep(1.5)
            self.duty(0)
            sleep(0.5)


def pagaidit(v):
    sleep(v)
