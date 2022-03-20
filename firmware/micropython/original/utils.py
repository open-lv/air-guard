import uasyncio
from machine import Signal, PWM, unique_id
from utime import ticks_ms
import logging
import machine
import math
import random

# For AirGuardIotMQTTClient
from umqtt.simple import MQTTClient


class LEDSignal(Signal):

    def ieslegt(self):
        self.on()

    def izslegt(self):
        self.off()


class LEDPWMSignal(PWM):
    on_duty = 1023

    def __init__(self, pin, on_duty=1023):
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
        self.generate_personality_tones()
        self.init(freq=1000, duty=0)

    def generate_personality_tones(self):
        random.seed(int.from_bytes(machine.unique_id(), "little"))
        self.startup_melody = self.generate_melody(length=5)
        self.alarm_melody = self.generate_melody(length=7)
        # short => has to be audible
        self.calibrate_melody = self.generate_melody(length=3, ns=800)
        self.button_melody = self.generate_melody(length=1, ns=800)

    def generate_melody(self, length=5, ns=500, ne=1500, ds=60, de=90):
        a = [random.randint(ns, ne) for i in range(length)]
        b = [int(random.uniform(ds, de)) for i in range(length)]
        s = list(zip(a, b))
        logging.getLogger("buzzer").debug("Generated tones: "+str(s))
        return s

    async def playback_melody(self, melody, duty=800, mul=0.0015):
        logging.getLogger("buzzer").debug("playing melody of "+str(melody))
        self.duty(duty)
        for freq, dur in melody:
            self.freq(freq)
            await uasyncio.sleep(dur*mul)
        self.duty(0)

    async def startup_beep(self):
        logging.getLogger("buzzer").info("startup beep")
        await self.playback_melody(self.startup_melody)

    async def short_beep(self):
        logging.getLogger("buzzer").info("short beep")
        await self.playback_melody(self.button_melody)

    async def long_beep(self):
        logging.getLogger("buzzer").info("long beep")
        await self.playback_melody(self.calibrate_melody)

    async def high_co2_level_alert(self):
        logging.getLogger("buzzer").info("high co2th level")
        await self.playback_melody(self.alarm_melody)


async def pagaidit(v):
    await uasyncio.sleep(v)


class ButtonEventHandler:
    """"""
    signal = None
    DEBOUNCE_TIME_MS = 10
    LONG_PRESS_TIME_MS = 5000
    posedge_debounce_time = 0
    posedge_state = False
    negedge_state = False
    negedge_debounce_time = 0
    negedge_on_latched = False
    longpress_start_time = 0
    longpress_on_latched = False
    longpress_state = False

    def __init__(self, signal):
        self.signal = signal
        self.log = logging.getLogger("btn")

    def posedge(self):
        """Returns True for one invocation after positive edge has been detected"""
        on = self.signal.value()
        if on and not self.posedge_state:
            self.posedge_state = True
            self.posedge_debounce_time = ticks_ms()
            return True
        elif not on and self.posedge_state and (ticks_ms() - self.posedge_debounce_time) > self.DEBOUNCE_TIME_MS:
            self.posedge_state = False

        return False

    def negedge(self):
        """Returns True for one invocation after negative edge has been detected"""
        on = self.signal.value()

        if on and not self.negedge_on_latched:
            self.negedge_debounce_time = ticks_ms()
            self.negedge_on_latched = True
            self.negedge_state = False

        if not on and self.negedge_on_latched and (ticks_ms() - self.negedge_debounce_time) > self.DEBOUNCE_TIME_MS:
            self.negedge_on_latched = False
            if not self.negedge_state:
                self.negedge_state = True
                return True

        return False

    def longpress(self):
        """Returns True for one invocation after a long press has been detected"""
        on = self.signal.value()
        if on and not self.longpress_on_latched:
            self.longpress_on_latched = True
            self.longpress_state = False
            self.longpress_start_time = ticks_ms()

        elif on and self.longpress_on_latched and (ticks_ms() - self.longpress_start_time) > self.LONG_PRESS_TIME_MS:
            if not self.longpress_state:
                self.longpress_state = True
                return True
        elif not on and (ticks_ms() - self.longpress_start_time) > self.DEBOUNCE_TIME_MS:
            self.longpress_on_latched = False
            self.longpress_state = False

        return False


# fade in/out animation max brightness
FMAX = 1023
FMID = 256
FMIN = 128

# fade in/out animation step size per tick
FS = 256


class EyeAnimation:
    """Handles animation of eye brightnesses.
    Expected usage:
    anim = EyeAnimation(pwm_left, pwm_right, [EyeAnimation.FADE_IN, EyeAnimation.FADE_OUT])
    while anim.tick():
        pass

    Of course, tick() can be called periodically- it returns True if animation is still in progress and False
    if animation has finished
    """

    FADE_IN = 1
    FADE_OUT = 2
    LEFT_TO_RIGHT = 3
    RIGHT_TO_LEFT = 4
    BLINK = 5

    _l = None
    _r = None
    _anim = None
    _anim_tick = 0
    _anim_max_tick = 0
    _curr_anim = 0

    # list of (left, right) duty cycles for each animation step
    _anim_seq = []

    # fade in animation- fades both eyes in
    # exponential curve
    _FADE_IN_SEQ = list(map(lambda x: int(math.pow(FMAX, x / FMAX)), range(FMIN, FMAX, FS))) + [FMAX]
    _FADE_IN_ANIM = list(zip(_FADE_IN_SEQ, _FADE_IN_SEQ))

    _FADE_OUT_SEQ = list(map(lambda x: int(math.pow(FMAX, x / FMAX)), range(FMAX, FMIN, -FS)))

    # fade out animation- fades both eyes out
    _FADE_OUT_ANIM = list(zip(_FADE_OUT_SEQ, _FADE_OUT_SEQ))
    _EMPTY_SEQ = [FMIN] * 2
    _FULL_SEQ = [FMAX] * 2

    _LEFT_TO_RIGHT_ANIM = list(zip(
        [FMID, FMIN, FMIN, FMIN, FMIN, FMIN, FMIN, FMID, FMAX],
        [FMID, FMIN, FMID, FMAX, FMAX, FMAX, FMAX, FMAX, FMAX],
    ))
    _RIGHT_TO_LEFT_ANIM = list(zip(
        [FMID, FMIN, FMID, FMAX, FMAX, FMAX, FMAX, FMAX, FMAX],
        [FMID, FMIN, FMIN, FMIN, FMIN, FMIN, FMIN, FMID, FMAX],
    ))

    _ANIM_MAP = {
        FADE_IN: _FADE_IN_ANIM,
        FADE_OUT: _FADE_OUT_ANIM,
        LEFT_TO_RIGHT: _LEFT_TO_RIGHT_ANIM,
        RIGHT_TO_LEFT: _RIGHT_TO_LEFT_ANIM,
        BLINK: list(zip([FMAX, FMIN, FMAX], [FMAX, FMIN, FMAX]))
    }

    def __init__(self, l, r, anim):
        self.l = l
        self.r = r
        if type(anim) is list:
            self.anim = anim
        else:
            self.anim = [anim]
        self.advance()

    def advance(self):
        self._anim_tick = 0
        if self._curr_anim < len(self.anim):
            anim = self.anim[self._curr_anim]
            self._curr_anim += 1
            if anim in self._ANIM_MAP.keys():
                self._anim_seq = self._ANIM_MAP[anim]
                self._anim_max_tick = len(self._anim_seq)
                return True
            else:
                logging.getLogger("main").error("unknown animation")
                return False
        return False

    def tick(self):
        if self._anim_tick < self._anim_max_tick:
            v = self._anim_seq[self._anim_tick]
            self.l.duty(v[0])
            self.r.duty(v[1])
            self._anim_tick += 1
            return True
        return self.advance()
