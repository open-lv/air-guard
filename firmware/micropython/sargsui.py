import logging
import uasyncio
from utime import ticks_ms
from utils import ButtonEventHandler, EyeAnimation, Buzzer


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
    INIT_SCREEN = 0
    MAIN_SCREEN = 1
    CALIBRATION_SCREEN = 2
    INTRO_SCREEN = 3
    WARMUP_SCREEN = 4
    OPEN_WINDOW_SCREEN = 5
    LARGE_PPM_SCREEN = 6
    SCREEN_END = 7


class SargsUIException(Exception):
    pass


class SargsUI:
    co2_measurement = None
    temperature_measurement = None
    co2_level = CO2Level.UNKNOWN
    wifi_state = WiFiState.UNCONFIGURED
    current_screen = ScreenState.INIT_SCREEN
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
    frame_display_ms = 50

    def __init__(self, screen, btn_signal, buzzer, ldr, left_eye, right_eye):
        self.log = logging.getLogger("screen")
        self.buzzer: Buzzer = buzzer
        self.screen = screen
        self.btn_signal = btn_signal
        self.ldr = ldr
        self.led_left_eye = left_eye
        self.led_right_eye = right_eye
        self.main_screen_btn_handler = ButtonEventHandler(self.btn_signal)
        self.cal_screen_btn_handler = ButtonEventHandler(self.btn_signal)

    def set_co2_measurement(self, m):
        self.co2_measurement = m

    def set_temperature_measurement(self, m):
        self.temperature_measurement = m

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

    async def update(self):
        self.process_ldr()
        if self.eye_animation and not self.eye_animation.tick():
            self.eye_animation = None

        if self.eye_animation is None and self.btn_signal.value():
            self.eye_animation = EyeAnimation(self.led_left_eye, self.led_right_eye,
                                              [EyeAnimation.FADE_IN, EyeAnimation.FADE_OUT])

        self.screen.drawFill(0)
        screen_fn_map = {
            ScreenState.INIT_SCREEN: self.draw_init_screen,
            ScreenState.MAIN_SCREEN: self.draw_main_screen,
            ScreenState.CALIBRATION_SCREEN: self.draw_calibration_screen,
            ScreenState.INTRO_SCREEN: self.draw_intro_screen,
            ScreenState.WARMUP_SCREEN: self.draw_warmup_screen,
            ScreenState.OPEN_WINDOW_SCREEN: self.draw_open_window_screen,
            ScreenState.LARGE_PPM_SCREEN: self.draw_large_ppm_screen
        }
        if self.current_screen in screen_fn_map.keys():
            await screen_fn_map[self.current_screen]()
        self.screen.flush()

        # if CO2 level has just become high
        if self.co2_level == CO2Level.HIGH and self.prev_co2_level != self.co2_level:
            # end we haven't alerted for some time
            if (ticks_ms() - self.high_co2_alert_time) > self.HIGH_CO2_ALERT_DEBOUNCE_MS:
                self.log.info("high co2 level alert triggered")
                await self.buzzer.high_co2_level_alert()
                self.high_co2_alert_time = ticks_ms()
        self.prev_co2_level = self.co2_level

        if self.frame_display_ms > 0:
            await uasyncio.sleep_ms(self.frame_display_ms)

    init_screen_frame = 0

    async def draw_init_screen(self):
        explosion_range = list(range(0, 11))
        fn = "/assets/splash/intro%d.png" % explosion_range[self.init_screen_frame]
        self.screen.drawPng(0, 0, fn)
        self.init_screen_frame += 1
        if self.init_screen_frame == len(explosion_range):
            self.screen.flush()
            await uasyncio.sleep_ms(1000)
            self.init_screen_frame = 0
            self.current_screen = ScreenState.INTRO_SCREEN
            self.eye_animation = EyeAnimation(self.led_left_eye, self.led_right_eye, [EyeAnimation.FADE_IN])

    intro_screen_frame = 0

    async def draw_intro_screen(self):
        # don't do anything until eye animation finishes
        if self.eye_animation:
            return
        intro_range = list(range(11, 34)) + [0]
        fn = "/assets/splash/intro%d.png" % intro_range[self.intro_screen_frame]
        self.screen.drawPng(0, 0, fn)
        self.intro_screen_frame += 1
        if self.intro_screen_frame == len(intro_range):
            self.eye_animation = EyeAnimation(self.led_left_eye, self.led_right_eye, [EyeAnimation.FADE_OUT])
            self.intro_screen_frame = 0
            self.current_screen = ScreenState.WARMUP_SCREEN

    heart_frame = 0
    heart_next_ticks_ms = 0
    h_range = list(reversed(list(range(1, 5))))

    async def draw_main_screen(self):
        if self.main_screen_btn_handler.longpress():
            await self.buzzer.short_beep()
            self.log.info("switching to cal screen")
            self.select_cal_screen()

        self.screen.drawText(58, -11, "%d C" % self.temperature_measurement, 0xffffff, "graphik_bold16", 1, 1)
        self.screen.drawCircle(102, 3, 3, 0, 360, False, 0xFFFFFF)
        ppm_t = str(self.co2_measurement)
        self.screen.drawText(48, 20, ppm_t, 0xffffff, "graphik_bold20", 1, 1)
        #self.screen.drawText(0, 37, "PPM", 0xffffff, "graphik_bold12", 1, 1)
        self.screen.drawPng(0,47,'/assets/ppm/ppm17.png')

        fn = "/assets/beating-heart/sirds%d.png" % self.h_range[self.heart_frame]
        self.screen.drawPng(0, 0, fn)
        if self.heart_next_ticks_ms == 0:
            self.heart_next_ticks_ms = ticks_ms() + 50

        heart_periods_ms = {
            CO2Level.LOW: 700,
            CO2Level.UNKNOWN: 700,
            CO2Level.MEDIUM: 600,
            CO2Level.HIGH: 500,
        }
        if ticks_ms() > self.heart_next_ticks_ms:
            self.heart_frame += 1
        if self.heart_frame == len(self.h_range):
            self.heart_frame = 0
            self.heart_next_ticks_ms += heart_periods_ms[self.co2_level]
        else:
            self.heart_next_ticks_ms += 50

        if self.co2_level == CO2Level.MEDIUM or self.co2_level == CO2Level.HIGH:
            self.current_screen = ScreenState.OPEN_WINDOW_SCREEN
            await self.buzzer.short_beep()
            self.frame_display_ms = 50
            self.eye_animation = EyeAnimation(self.led_left_eye, self.led_right_eye,
                                              [EyeAnimation.FADE_IN, EyeAnimation.FADE_OUT])

        if self.co2_level not in self.CO2_LEVEL_DESC.keys():
            raise SargsUIException("Invalid CO2 level provided: %s" % (str(self.co2_level)))

        if self.wifi_state not in self.WIFI_STATE_DESC.keys():
            raise SargsUIException("Invalid WiFi state provided: %s" % str(self.wifi_state))

    warmup_frame = 0

    async def draw_warmup_screen(self):
        f_range = list(range(0, 12))
        fn = "/assets/self-test/selftest%d.png" % f_range[self.warmup_frame]
        self.screen.drawPng(0, 0, fn)
        self.warmup_frame += 1
        if self.warmup_frame == len(f_range):
            self.warmup_frame = 0

        if self.co2_measurement is not None:
            self.select_main_screen()
            self.frame_display_ms = 0

    open_window_frame = 0
    open_window_range = list(range(0, 27))

    async def draw_open_window_screen(self):
        fn = "/assets/open-window/open%d.png" % self.open_window_range[self.open_window_frame]
        self.screen.drawPng(0, 0, fn)
        self.open_window_frame += 1

        if self.open_window_frame == len(self.open_window_range):
            await self.buzzer.short_beep()
            self.current_screen = ScreenState.LARGE_PPM_SCREEN
            self.open_window_frame = 0
            self.large_ppm_enter_ticks_ms = ticks_ms()
            self.frame_display_ms = 300

    large_ppm_enter_ticks_ms = 0
    large_ppm_ctr = 0

    async def draw_large_ppm_screen(self):
        ppm_t = str(self.co2_measurement)
        idx = self.large_ppm_ctr % 2
        self.large_ppm_ctr += 1

        fonts = ["graphik_bold16", "graphik_bold20"]
        x = (self.screen.width() - self.screen.getTextWidth(ppm_t, fonts[idx])) // 2
        y = (self.screen.height() - self.screen.getTextHeight(ppm_t, fonts[idx])) // 2 - 5

        self.screen.drawText(x, y, ppm_t, 0xffffff, fonts[idx])

        if self.co2_level == CO2Level.LOW:
            await self.buzzer.short_beep()
            self.select_main_screen()
            self.frame_display_ms = 0
        elif ticks_ms() > (self.large_ppm_enter_ticks_ms + 20 * 1000):
            await self.buzzer.short_beep()
            self.eye_animation = EyeAnimation(self.led_left_eye, self.led_right_eye,
                                              [EyeAnimation.FADE_IN, EyeAnimation.FADE_OUT])
            self.current_screen = ScreenState.OPEN_WINDOW_SCREEN
            self.frame_display_ms = 50

    async def draw_hcenter_text(self, y, text):
        """Draws a horizontally centered line of text at specified offset from top"""
        x = (self.screen.width() - self.screen.getTextWidth(text)) // 2
        self.screen.drawText(x, y, text)

    async def draw_calibration_screen(self):

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
                await self.buzzer.short_beep()
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
                    await self.buzzer.long_beep()
                else:
                    # no btn selected, go back to main screen
                    await self.buzzer.short_beep()
                    self.log.info("returning to main screen due to no button")
                    self.select_main_screen()

        if not self.calibration_requested:
            await self.draw_hcenter_text(5, "Vai sakt")
            await self.draw_hcenter_text(25, "kalibraciju?")

            sel_btn = self.cal_sel_btn  # 1 = no, 2 = yes
            await self.draw_button(10, 45, "Ne", sel_btn == 1)
            await self.draw_button(100, 45, "Ja", sel_btn == 2)
        else:
            self.log.info("user-requested calibration initiated")
            await self.draw_hcenter_text(5, "Kalibracija")
            await self.draw_hcenter_text(25, "uzsakta!")
            # sargs.py will return screen to main screen once it processes the calibration_requested flag

    async def draw_button(self, x, y, text, selected):
        self.screen.drawText(x + 3, y + 3, text)
        if selected:
            self.screen.drawRect(x, y, self.screen.getTextWidth(text) + 7,
                                 self.screen.getTextHeight(text) + 7, False, 0xffffff)
