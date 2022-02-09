import uasyncio
from machine import Signal, PWM


class LEDSignal(Signal):

    def ieslegt(self):
        self.on()

    def izslegt(self):
        self.off()


class LEDPWMSignal(PWM):
    on_duty = 1024

    def __init__(self, pin, on_duty=1024):
        super().__init__(pin)
        self.init(freq=1000, duty=0)
        self.on_duty = on_duty

    def on(self):
        self.duty(self.on_duty)

    def off(self):
        self.duty(0)

    def value(self, *args):
        if len(args) > 0:
            # setter
            if args[0]:
                self.on()
            else:
                self.off()
        else:
            # getter
            return self.duty() > 0

    def ieslegt(self):
        self.on()

    def izslegt(self):
        self.off()


class Buzzer(PWM):
    """Implements blocking methods for various beeps/tones"""

    def __init__(self, pin):
        super().__init__(pin)
        self.init(freq=1000, duty=0)

    async def startup_beep(self):
        self.duty(512)
        await uasyncio.sleep(0.5)
        self.duty(0)

    async def short_beep(self):
        self.duty(512)
        await uasyncio.sleep(0.1)
        self.duty(0)

    async def long_beep(self):
        self.duty(512)
        await uasyncio.sleep(0.7)
        self.duty(0)

    async def high_co2_level_alert(self):
        for i in range(3):
            self.duty(512)
            await uasyncio.sleep(1.5)
            self.duty(0)
            await uasyncio.sleep(0.5)


async def pagaidit(v):
    await uasyncio.sleep(v)
