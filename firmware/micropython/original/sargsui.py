import logging
import random
import sys
import time

import uasyncio
from utime import ticks_ms
from .utils import ButtonEventHandler, EyeAnimation, Buzzer
from . import plot

# uPy doesn't seem to support enums, this is probably better than passing constants around

class WiFiState:
    UNCONFIGURED = 1
    CONNECTING = 2
    CONNECTED = 3
    DISCONNECTED = 4
    ACCESS_POINT = 5

class InternetState:
    DISCONNECTED = 1
    CONNECTED = 2


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
    PLOT_SCREEN = 7
    OTA_UPDATE_SCREEN = 8
    SCREEN_END = 9


class SargsUIException(Exception):
    pass


class SargsUI:
    WIFI_STATE_DESC = {
        WiFiState.UNCONFIGURED: "nav konf.",
        WiFiState.ACCESS_POINT: "piekl. p.",
        WiFiState.DISCONNECTED: "atvienots",
        WiFiState.CONNECTING: "savienojas",
        WiFiState.CONNECTED: "savienots",
    }
    INTERNET_STATE_DESC = {
        InternetState.CONNECTED: "ir",
        InternetState.DISCONNECTED: "nav"
    }
    CO2_LEVEL_DESC = {
        CO2Level.LOW: "LABS GAISS!",
        CO2Level.MEDIUM: "ATVER LOGU!",
        CO2Level.HIGH: "AARGH!",
        CO2Level.UNKNOWN: "",
    }

    HEARTBEAT_PERIODS_MS = {
        CO2Level.LOW: 500,
        CO2Level.UNKNOWN: 500,
        CO2Level.MEDIUM: 400,
        CO2Level.HIGH: 300,
    }

    MAIN_SUBSCREENS = ["draw_main_large_heart_screen", "draw_main_small_heart_screen",
                       "draw_15min_plot_screen", "draw_1h_plot_screen", "draw_12h_plot_screen", "draw_24h_plot_screen",
                       "draw_network_screen", "draw_credits_screen",
                       ]

    def __init__(self, screen, btn_signal, buzzer, ldr, left_eye, right_eye):

        self.heart_frame = 0
        self.heart_next_ticks_ms = 0
        self.h_range = list(reversed(list(range(1, 5))))

        self.main_selected_subscreen = 0
        self.eye_next_blink_ticks_ms = 0
        self.co2_measurement = None
        self.temperature_measurement = None
        self.co2_level = CO2Level.UNKNOWN
        self.wifi_state = WiFiState.UNCONFIGURED
        self.internet_state = InternetState.DISCONNECTED
        self.current_screen = ScreenState.INIT_SCREEN
        self.calibration_requested = False
        self.ota_update_requested = False
        self.display_ip_address = None
        self.cal_sel_btn = 1
        self.ota_sel_btn = 1
        self.main_screen_btn_handler = None
        self.cal_screen_btn_handler = None
        self.ota_screen_btn_handler = None
        self.cal_screen_negedge_count = 0
        self.ota_screen_negedge_count = 0
        self.cal_screen_act_time = 0
        self.ota_screen_act_time = 0

        self.buzzer = None
        self.ldr = None
        self.led_left_eye = None
        self.led_right_eye = None
        self.eye_animation = None
        self.ldr_measurements = []
        # hysteresis/debounce time in ms for med->high CO2 level (so that alert does not repeat if the
        # CO2 measurement fluctuates around the limit
        self.HIGH_CO2_ALERT_DEBOUNCE_MS = 5 * 60 * 1000
        self.high_co2_alert_time = 0
        self.prev_co2_level = CO2Level.LOW
        self.frame_display_ms = 50

        self.plots = [
            ("15 min", plot.CO2Plotter(15, 128, 48)),
            ("1 h", plot.CO2Plotter(60, 128, 48)),
            ("12 h", plot.CO2Plotter(60 * 12, 128, 48)),
            ("24 h", plot.CO2Plotter(60 * 24, 128, 48))
        ]

        self.init_screen_frame = 0

        self.intro_screen_frame = 0

        self.warmup_frame = 0

        self.open_window_frame = 0
        self.open_window_range = list(range(0, 27))

        self.large_ppm_enter_ticks_ms = 0
        self.large_ppm_ctr = 0

        self.large_heart_frame = 0
        self.large_heart_range = list(range(1, 5))
        self.large_heart_next_ticks_ms = 0

        self.credits_frame = 0
        self.credits_frame_range = list(range(0, 25))
        self.credits_y_pos = 0
        self.credits_next_ticks_ms = 0

        self.log = logging.getLogger("screen")
        self.buzzer: Buzzer = buzzer
        self.screen = screen
        self.btn_signal = btn_signal
        self.ldr = ldr
        self.led_left_eye = left_eye
        self.led_right_eye = right_eye

        self.led_left_eye.on()
        self.led_right_eye.on()

        self.main_screen_btn_handler = ButtonEventHandler(self.btn_signal)
        self.cal_screen_btn_handler = ButtonEventHandler(self.btn_signal)
        self.ota_screen_btn_handler = ButtonEventHandler(self.btn_signal)

        self.runtime_dir = __file__[:__file__.rindex("/")]

        self.update_available = False
        self.update_prompt_shown = False
        self.latest_version = None

    def set_co2_measurement(self, m):
        self.co2_measurement = m
        for p in self.plots:
            p[1].add_measurement(m)

    def set_temperature_measurement(self, m):
        self.temperature_measurement = m

    def set_wifi_state(self, s):
        self.wifi_state = s

    def set_internet_state(self, s):
        self.internet_state = s

    def set_display_ip_address(self, ip):
        self.display_ip_address = ip

    def set_co2_level(self, l):
        self.co2_level = l

    def select_main_screen(self):
        self.current_screen = ScreenState.MAIN_SCREEN
        self.calibration_requested = False
        self.frame_display_ms = 0

    def select_last_main_subscreen(self):
        self.main_selected_subscreen = len(self.MAIN_SUBSCREENS) - 2

    def select_cal_screen(self):
        self.cal_screen_negedge_count = 0
        self.cal_screen_act_time = ticks_ms()
        self.current_screen = ScreenState.CALIBRATION_SCREEN

    def select_ota_screen(self):
        self.ota_screen_act_time = ticks_ms()
        self.current_screen = ScreenState.OTA_UPDATE_SCREEN

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
                self.trigger_random_eye_animation()
            del self.ldr_measurements[0]

    def trigger_random_eye_animation(self):
        if self.eye_animation is None:
            choices = [EyeAnimation.LEFT_TO_RIGHT, EyeAnimation.RIGHT_TO_LEFT, EyeAnimation.BLINK]
            self.eye_animation = EyeAnimation(self.led_left_eye, self.led_right_eye, random.choice(choices))

    async def update(self):
        self.process_ldr()
        await uasyncio.sleep_ms(0)
        if self.eye_animation and not self.eye_animation.tick():
            self.eye_animation = None

        if self.eye_animation is None:
            if self.btn_signal.value():
                self.trigger_random_eye_animation()
            elif ticks_ms() > self.eye_next_blink_ticks_ms:
                # choose a random animation for ~1/4 of the blinks
                if random.random() < 0.25:
                    self.trigger_random_eye_animation()
                else:
                    self.eye_animation = EyeAnimation(self.led_left_eye, self.led_right_eye,
                                                  [EyeAnimation.BLINK])
                # blink an average of 12x per min with slight variance
                mean_blinks_per_min = 12
                mean_blink_period = 60000 / mean_blinks_per_min
                blink_dev = mean_blink_period * 0.1
                self.eye_next_blink_ticks_ms = ticks_ms() + random.randint(
                    int(mean_blink_period - blink_dev), int(mean_blink_period + blink_dev))
        else:
            # reset the next blink time while animation is in progress
            self.eye_next_blink_ticks_ms = ticks_ms() + 5000

        is_ota_screen = self.current_screen == ScreenState.OTA_UPDATE_SCREEN
        if self.update_available and not self.update_prompt_shown and not is_ota_screen:
            self.select_ota_screen()

        self.screen.drawFill(0)
        await uasyncio.sleep_ms(0)

        screen_fn_map = {
            ScreenState.INIT_SCREEN: self.draw_init_screen,
            ScreenState.MAIN_SCREEN: self.draw_main_screen,
            ScreenState.CALIBRATION_SCREEN: self.draw_calibration_screen,
            ScreenState.INTRO_SCREEN: self.draw_intro_screen,
            ScreenState.WARMUP_SCREEN: self.draw_warmup_screen,
            ScreenState.OPEN_WINDOW_SCREEN: self.draw_open_window_screen,
            ScreenState.LARGE_PPM_SCREEN: self.draw_large_ppm_screen,
            ScreenState.PLOT_SCREEN: self.draw_plot_screen,
            ScreenState.OTA_UPDATE_SCREEN: self.draw_ota_update_screen,
        }
        if self.current_screen in screen_fn_map.keys():
            await screen_fn_map[self.current_screen]()
        self.screen.flush()
        await uasyncio.sleep_ms(0)

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

    async def draw_init_screen(self):
        explosion_range = list(range(0, 11))
        fn = "/assets/splash/intro%d.png" % explosion_range[self.init_screen_frame]
        await self.drawPng(0, 0, fn)
        self.init_screen_frame += 1
        if self.init_screen_frame == len(explosion_range):
            self.screen.flush()
            await uasyncio.sleep_ms(1000)
            self.init_screen_frame = 0
            self.current_screen = ScreenState.INTRO_SCREEN
            self.eye_animation = EyeAnimation(self.led_left_eye, self.led_right_eye, [EyeAnimation.FADE_IN])

    async def draw_intro_screen(self):
        # don't do anything until eye animation finishes
        if self.eye_animation:
            return
        intro_range = list(range(11, 34)) + [0]
        fn = "/assets/splash/intro%d.png" % intro_range[self.intro_screen_frame]
        await self.drawPng(0, 0, fn)
        self.intro_screen_frame += 1
        if self.intro_screen_frame == len(intro_range):
            self.intro_screen_frame = 0
            self.current_screen = ScreenState.WARMUP_SCREEN

    async def draw_main_screen(self):
        if self.main_screen_btn_handler.longpress():
            await self.buzzer.short_beep()
            self.log.info("switching to cal screen")
            self.select_cal_screen()
        elif self.main_screen_btn_handler.negedge():
            await self.buzzer.short_beep()
            self.main_selected_subscreen += 1
            if self.main_selected_subscreen == len(self.MAIN_SUBSCREENS):
                self.main_selected_subscreen = 0

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

        subscreen_fn = getattr(self, self.MAIN_SUBSCREENS[self.main_selected_subscreen])
        await subscreen_fn()


    async def draw_main_small_heart_screen(self):
        # temperature with degree symbol
        temp_num = str(self.temperature_measurement)
        temp_text = temp_num + " C"
        temp_font = "graphik_bold16"
        temp_x = 58
        self.screen.drawText(temp_x, -11, temp_text, 0xffffff, temp_font, 1, 1)
        await uasyncio.sleep_ms(0)
        # position of degree symbol based on displayed value
        deg_x = temp_x + self.screen.getTextWidth(temp_num, temp_font) + 3
        await uasyncio.sleep_ms(0)
        self.screen.drawCircle(deg_x, 3, 3, 0, 360, False, 0xFFFFFF)
        await uasyncio.sleep_ms(0)

        # CO2 sensor measurement
        ppm_t = str(self.co2_measurement)
        self.screen.drawText(48, 20, ppm_t, 0xffffff, "graphik_bold20", 1, 1)
        await uasyncio.sleep_ms(0)

        # PPM text
        await self.drawPng(0, 47, '/assets/ppm/ppm17.png')

        fn = "/assets/beating-heart/sirds%d.png" % self.h_range[self.heart_frame]
        await self.drawPng(0, 0, fn)

        if ticks_ms() > self.heart_next_ticks_ms:
            self.heart_frame += 1
            if self.heart_frame == len(self.h_range):
                self.heart_frame = 0
                self.heart_next_ticks_ms = ticks_ms() + self.HEARTBEAT_PERIODS_MS[self.co2_level]
            else:
                self.heart_next_ticks_ms = ticks_ms() + 50

    async def draw_warmup_screen(self):
        f_range = list(range(0, 9))
        fn = "/assets/beating-heart/ekg%d.png" % f_range[self.warmup_frame]
        await self.drawPng(0, 0, fn)
        self.warmup_frame += 1
        if self.warmup_frame == len(f_range):
            self.warmup_frame = 0

        if self.co2_measurement is not None:
            self.select_main_screen()

    async def draw_open_window_screen(self):
        fn = "/assets/open-window/open%d.png" % self.open_window_range[self.open_window_frame]
        await self.drawPng(0, 0, fn)
        self.open_window_frame += 1

        if self.open_window_frame == len(self.open_window_range):
            await self.buzzer.short_beep()
            self.current_screen = ScreenState.LARGE_PPM_SCREEN
            self.open_window_frame = 0
            self.large_ppm_enter_ticks_ms = ticks_ms()
            self.frame_display_ms = 300

    async def draw_large_ppm_screen(self):
        ppm_t = str(self.co2_measurement)
        idx = self.large_ppm_ctr % 2
        self.large_ppm_ctr += 1

        fonts = ["graphik_bold16", "graphik_bold20"]
        x = (self.screen.width() - self.screen.getTextWidth(ppm_t, fonts[idx])) // 2
        await uasyncio.sleep_ms(0)
        y = (self.screen.height() - self.screen.getTextHeight(ppm_t, fonts[idx])) // 2 - 5
        await uasyncio.sleep_ms(0)


        self.screen.drawText(x, y, ppm_t, 0xffffff, fonts[idx])
        await uasyncio.sleep_ms(0)

        if self.co2_level == CO2Level.LOW:
            await self.buzzer.short_beep()
            self.select_main_screen()
        elif ticks_ms() > (self.large_ppm_enter_ticks_ms + 20 * 1000):
            await self.buzzer.short_beep()
            self.eye_animation = EyeAnimation(self.led_left_eye, self.led_right_eye,
                                              [EyeAnimation.FADE_IN, EyeAnimation.FADE_OUT])
            self.current_screen = ScreenState.OPEN_WINDOW_SCREEN
            self.frame_display_ms = 50

    async def draw_hcenter_text(self, y, text):
        """Draws a horizontally centered line of text at specified offset from top"""
        x = (self.screen.width() - self.screen.getTextWidth(text)) // 2
        await uasyncio.sleep_ms(0)
        self.screen.drawText(x, y, text)
        await uasyncio.sleep_ms(0)

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
        self.screen.drawText(x + 2, y + 2, text)
        await uasyncio.sleep_ms(0)
        if selected:
            self.screen.drawRect(x, y, self.screen.getTextWidth(text) + 5,
                                 self.screen.getTextHeight(text) + 5, False, 0xffffff)
            await uasyncio.sleep_ms(0)

#     TODO - replace current main view with this, current main view as second / third smth view

    async def draw_main_large_heart_screen(self):
        """"
        ###### VIEW1 ##### LARGE BEATING HEART + PPM
        """

        fn = "/assets/beating-heart/liela-sirds%d.png" % self.large_heart_range[self.large_heart_frame]
        await self.drawPng(0, 0, fn)

        if ticks_ms() > self.large_heart_next_ticks_ms:
            self.large_heart_frame += 1
            if self.large_heart_frame == len(self.large_heart_range):
                self.large_heart_frame = 0
                self.large_heart_next_ticks_ms = ticks_ms() + self.HEARTBEAT_PERIODS_MS[self.co2_level]
            else:
                self.large_heart_next_ticks_ms = ticks_ms() + 50

        await self.drawPng(49, 46, '/assets/ppm/ppmw10.png')
        ppm_text = str(self.co2_measurement)
        ppm_font = "graphik_bold20"
        ppm_text_w = self.screen.getTextWidth(ppm_text, ppm_font)
        await uasyncio.sleep_ms(0)
        self.screen.drawText((self.screen.width() - ppm_text_w) // 2, 2, ppm_text, 0x000000, ppm_font, 1, 1)
        await uasyncio.sleep_ms(0)

        temp_text = str(self.temperature_measurement)
        temp_font = "7x5"
        temp_text_w = self.screen.getTextWidth(temp_text, temp_font)
        await uasyncio.sleep_ms(0)
        temp_x = 58
        self.screen.drawText(temp_x, 0, temp_text, 0xFFFFFF, temp_font, 1, 1)
        await uasyncio.sleep_ms(0)
        self.screen.drawCircle(temp_x + temp_text_w + 2 , 1, 1, 0, 360, False, 0xFFFFFF)
        await uasyncio.sleep_ms(0)

    async def draw_credits_screen(self):
        fn_templ = "/assets/credits/credits%d.png"
        fn = fn_templ % self.credits_frame_range[self.credits_frame]
        await self.drawPng(0, self.credits_y_pos, fn)
        if self.credits_frame != len(self.credits_frame_range) - 1 and self.credits_y_pos != 0:
            # also draw the next sprite
            fn = fn_templ % self.credits_frame_range[self.credits_frame + 1]
            await self.drawPng(0, self.credits_y_pos + 64, fn)

        if self.credits_next_ticks_ms != 0 and ticks_ms() > self.credits_next_ticks_ms:
            # scroll by credits
            self.credits_y_pos -= 3
            if self.credits_y_pos < -64:
                self.credits_frame += 1
                self.credits_y_pos = 0
                if self.credits_frame == len(self.credits_frame_range):
                    # end of credits, switch back to main screen
                    self.credits_next_ticks_ms = 0
                    self.credits_frame = 0
                    self.main_selected_subscreen = 0

        self.credits_next_ticks_ms = ticks_ms() + 5

    async def drawPng(self, x_pos, y_pos, fn):
        self.screen.drawPng(x_pos, y_pos, self.runtime_dir + fn)
        await uasyncio.sleep_ms(0)

    async def draw_15min_plot_screen(self):
        await self.draw_plot_screen(0)

    async def draw_1h_plot_screen(self):
        if not self.plots[1][1].have_enough_data():
            self.select_last_main_subscreen()
        else:
            await self.draw_plot_screen(1)

    async def draw_12h_plot_screen(self):
        if not self.plots[2][1].have_enough_data():
            self.select_last_main_subscreen()
        else:
            await self.draw_plot_screen(2)

    async def draw_24h_plot_screen(self):
        if not self.plots[3][1].have_enough_data():
            self.select_last_main_subscreen()
        else:
            await self.draw_plot_screen(3)

    async def draw_plot_screen(self, selected_plot):
        sp = self.plots[selected_plot]
        text = "%s " % sp[0]
        self.screen.drawText(self.screen.width() - self.screen.getTextWidth(text),
                             self.screen.height() - self.screen.getTextHeight(text) - 2,
                             text)
        await uasyncio.sleep_ms(0)
        if sp[1].have_enough_data():
            await sp[1].plot_data(self.screen, 0)
        else:
            await self.draw_hcenter_text(24, "Nepietiek datu!")

    async def draw_network_screen(self):
        await self.draw_hcenter_text(10, "WiFi: " + self.WIFI_STATE_DESC[self.wifi_state])
        await self.draw_hcenter_text(30, "Internets: " + self.INTERNET_STATE_DESC[self.internet_state])

        if self.display_ip_address:
            await self.draw_hcenter_text(50, "IP: " + self.display_ip_address)

    async def draw_ota_update_screen(self):

        screen_timeout = (ticks_ms() - self.ota_screen_act_time) > 60 * 1000
        if not self.ota_update_requested and screen_timeout and not self.ota_screen_btn_handler.signal.value():
            self.log.info("returning to main screen due to timeout")
            self.update_prompt_shown = True
            self.select_main_screen()

        if not self.ota_update_requested:
            # select yes/no on button release
            if self.ota_screen_btn_handler.negedge():
                self.ota_screen_act_time = ticks_ms()
                await self.buzzer.short_beep()
                self.ota_sel_btn += 1
                if self.ota_sel_btn == 3:
                    self.ota_sel_btn = 1

            if self.ota_screen_btn_handler.longpress():
                self.update_prompt_shown = True
                if self.ota_sel_btn == 2:
                    self.log.info("user requested ota")
                    self.ota_update_requested = True
                    await self.buzzer.long_beep()
                else:
                    # no btn selected, go back to main screen
                    await self.buzzer.short_beep()
                    self.log.info("returning to main screen due to no button")
                    self.select_main_screen()

        if not self.ota_update_requested:
            await self.draw_hcenter_text(0, "Pieejama jauna")
            await self.draw_hcenter_text(14, "versija: " + self.latest_version)
            await self.draw_hcenter_text(28, "Sakt atjauninasanu?")

            sel_btn = self.ota_sel_btn  # 1 = no, 2 = yes
            await self.draw_button(10, 45, "Ne", sel_btn == 1)
            await self.draw_button(100, 45, "Ja", sel_btn == 2)
        else:
            self.log.info("ota initiated by user request")
            await self.draw_hcenter_text(5, "Atjauninasana")
            await self.draw_hcenter_text(25, "uzsakta!")
            # sargs.py will return screen to main screen once it processes the ota_update_requested flag

