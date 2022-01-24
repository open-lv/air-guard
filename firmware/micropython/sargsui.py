import logging
from utime import ticks_ms, sleep
import math

# uPy doesn't seem to support enums, this is probably better than passing constants around


class WiFiState:
    UNCONFIGURED = 1
    CONNECTING = 2
    CONNECTED = 3


class CO2Level:
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    UNKNOWN = 4


class ScreenState:
    MAIN_SCREEN = 1
    CALIBRATION_SCREEN = 2
    SCREEN_END = 3


class SargsUIException(Exception):
    pass


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
FM = 512
# fade in/out animation step size per tick
FS = 48


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
    _FADE_IN_SEQ = list(map(lambda x: int(math.pow(FM, x/FM)), range(0, FM, FS))) + [FM]
    _FADE_IN_ANIM = list(zip(_FADE_IN_SEQ, _FADE_IN_SEQ))

    _FADE_OUT_SEQ = list(map(lambda x: int(math.pow(FM, x/FM)), range(FM, 0, -FS))) + [0]

    # fade out animation- fades both eyes out
    _FADE_OUT_ANIM = list(zip(_FADE_OUT_SEQ, _FADE_OUT_SEQ))
    _EMPTY_SEQ = [0] * 5
    _FULL_SEQ = [FM] * 5

    _LEFT_TO_RIGHT_ANIM = list(zip(
        _FADE_IN_SEQ + _FULL_SEQ + _FADE_OUT_SEQ + _EMPTY_SEQ,
        _EMPTY_SEQ + _FADE_IN_SEQ + _FULL_SEQ + _FADE_OUT_SEQ
    )) + [(0, 0)]
    _RIGHT_TO_LEFT_ANIM = list(zip(
        _EMPTY_SEQ + _FADE_IN_SEQ + _FULL_SEQ + _FADE_OUT_SEQ,
        _FADE_IN_SEQ + _FULL_SEQ + _FADE_OUT_SEQ + _EMPTY_SEQ,
    )) + [(0, 0)]

    _ANIM_MAP = {
        FADE_IN: _FADE_IN_ANIM,
        FADE_OUT: _FADE_OUT_ANIM,
        LEFT_TO_RIGHT: _LEFT_TO_RIGHT_ANIM,
        RIGHT_TO_LEFT: _RIGHT_TO_LEFT_ANIM
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


class SargsUI:
    co2_measurement = None
    co2_level = CO2Level.UNKNOWN
    wifi_state = WiFiState.UNCONFIGURED
    current_screen = ScreenState.MAIN_SCREEN
    calibration_requested = False
    WIFI_STATE_DESC = {
        WiFiState.UNCONFIGURED: "nav konf.",
        WiFiState.CONNECTING: "savienojas",
        WiFiState.CONNECTED: "savienots"
    }
    CO2_LEVEL_DESC = {
        CO2Level.LOW: "LABS GAISS!",
        CO2Level.MEDIUM: "ATVER LOGU!",
        CO2Level.HIGH: "AARGH!",
        CO2Level.UNKNOWN: "",
    }
    cal_sel_btn = 1
    main_screen_btn_handler = None
    cal_screen_btn_handler = None
    cal_screen_negedge_count = 0
    cal_screen_act_time = 0
    buzzer = None
    ldr = None
    led_left_eye = None
    led_right_eye = None
    eye_animation = None
    ldr_measurements = []
    # hysteresis/debounce time in ms for med->high CO2 level (so that alert does not repeat if the
    # CO2 measurement fluctuates around the limit
    HIGH_CO2_ALERT_DEBOUNCE_MS = 5 * 60 * 1000
    high_co2_alert_time = 0
    prev_co2_level = CO2Level.LOW

    def __init__(self, screen, btn_signal, buzzer, ldr, left_eye, right_eye):
        self.log = logging.getLogger("screen")
        self.buzzer = buzzer
        self.screen = screen
        self.btn_signal = btn_signal
        self.ldr = ldr
        self.led_left_eye = left_eye
        self.led_right_eye = right_eye
        self.main_screen_btn_handler = ButtonEventHandler(self.btn_signal)
        self.cal_screen_btn_handler = ButtonEventHandler(self.btn_signal)

    def set_co2_measurement(self, m):
        self.co2_measurement = m

    def set_wifi_state(self, s):
        self.wifi_state = s

    def set_co2_level(self, l):
        self.co2_level = l

    def select_main_screen(self):
        self.current_screen = ScreenState.MAIN_SCREEN
        self.calibration_requested = False

    def select_cal_screen(self):
        self.cal_screen_negedge_count = 0
        self.cal_screen_act_time = ticks_ms()
        self.current_screen = ScreenState.CALIBRATION_SCREEN

    def process_ldr(self):
        # invert the analog value so that higher values mean more brightness
        ldr_value = 4096 - self.ldr.read()
        self.ldr_measurements.append(ldr_value)

        if len(self.ldr_measurements) > 16:
            # subtract mean from the measurements
            buf = self.ldr_measurements.copy()
            mean = sum(buf) / len(buf)
            buf = list(map(lambda x: x - mean, buf))
            # detect peaks of at least X% of the measuring range
            if max(buf) > 0.05 * 4096:
                if self.eye_animation is None:
                    self.eye_animation = EyeAnimation(self.led_left_eye, self.led_right_eye,
                                                      [EyeAnimation.LEFT_TO_RIGHT, EyeAnimation.RIGHT_TO_LEFT])
            del self.ldr_measurements[0]

    def update(self):
        self.process_ldr()
        if self.eye_animation and not self.eye_animation.tick():
            self.eye_animation = None

        if self.eye_animation is None and self.btn_signal.value():
            self.eye_animation = EyeAnimation(self.led_left_eye, self.led_right_eye,
                                              [EyeAnimation.FADE_IN, EyeAnimation.FADE_OUT])

        self.screen.fill(0)
        screen_fn_map = {
            ScreenState.MAIN_SCREEN: self.draw_main_screen,
            ScreenState.CALIBRATION_SCREEN: self.draw_calibration_screen,
        }
        if self.current_screen in screen_fn_map.keys():
            screen_fn_map[self.current_screen]()
        self.screen.show()

        # if CO2 level has just become high
        if self.co2_level == CO2Level.HIGH and self.prev_co2_level != self.co2_level:
            # end we haven't alerted for some time
            if (ticks_ms() - self.high_co2_alert_time) > self.HIGH_CO2_ALERT_DEBOUNCE_MS:
                self.buzzer.high_co2_level_alert()
                self.high_co2_alert_time = ticks_ms()
        self.prev_co2_level = self.co2_level

    def draw_main_screen(self):
        if self.main_screen_btn_handler.longpress():
            self.buzzer.short_beep()
            self.log.info("switching to cal screen")
            self.select_cal_screen()

        if self.co2_measurement is None:
            self.screen.text("Sensors uzsilst", 0, 0)
        else:
            self.screen.text("CO2: %d ppm" % self.co2_measurement, 0, 0)

        if self.co2_level not in self.CO2_LEVEL_DESC.keys():
            raise SargsUIException("Invalid CO2 level provided: %s" % (str(self.co2_level)))
        self.screen.text(self.CO2_LEVEL_DESC[self.co2_level], 0, 20)

        if self.wifi_state not in self.WIFI_STATE_DESC.keys():
            raise SargsUIException("Invalid WiFi state provided: %s" % str(self.wifi_state))
        self.screen.text("Wi-Fi: %s" % self.WIFI_STATE_DESC[self.wifi_state], 0, 40)

    def draw_calibration_screen(self):

        # don't react to the negative edge of the long-press that was used to enter this screen
        if self.cal_screen_negedge_count == 0 and self.cal_screen_btn_handler.negedge():
            self.cal_screen_negedge_count += 1

        # go back to main screen after 30 seconds of inactivity
        screen_timeout = (ticks_ms() - self.cal_screen_act_time) > 30 * 1000
        if not self.calibration_requested and screen_timeout and not self.cal_screen_btn_handler.signal.value():
            self.log.info("returning to main screen due to timeout")
            self.select_main_screen()

        if not self.calibration_requested and self.cal_screen_negedge_count > 0:
            # select yes/no on button release
            if self.cal_screen_btn_handler.negedge():
                self.buzzer.short_beep()
                self.cal_screen_act_time = ticks_ms()
                self.cal_sel_btn += 1
                if self.cal_sel_btn == 3:
                    self.cal_sel_btn = 1

            if self.cal_screen_btn_handler.longpress():
                if self.cal_sel_btn == 2:
                    # yes selected, request calibration
                    self.log.info("user cal requested")
                    self.calibration_requested = True
                    self.cal_screen_act_time = ticks_ms()
                    self.buzzer.long_beep()
                else:
                    # no btn selected, go back to main screen
                    self.buzzer.short_beep()
                    self.log.info("returning to main screen due to no button")
                    self.select_main_screen()

        if not self.calibration_requested:
            self.screen.text("    Vai sakt", 0, 5)
            self.screen.text("  kalibraciju?", 0, 25)

            sel_btn = self.cal_sel_btn  # 1 = no, 2 = yes
            btn_pos = {1: (10, 48, 20, 12, 1),
                       2: (98, 48, 20, 12, 1)}

            self.screen.framebuf.rect(*btn_pos[sel_btn])
            self.screen.text("Ne", 12, 50)
            self.screen.text("Ja", 100, 50)
        else:
            self.log.info("user-requested calibration initiated")
            self.screen.text("   Kalibracija", 0, 5)
            self.screen.text("    uzsakta!", 0, 25)
            # sargs.py will return screen to main screen once it processes the calibration_requested flag
