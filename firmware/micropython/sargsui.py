import logging
from utime import ticks_ms


# uPy doesn't seem to support enums, this is probably better than passing constants around


class WiFiState:
    UNCONFIGURED = 1
    CONNECTING = 2
    CONNECTED = 3


class CO2Level:
    LOW = 1
    MEDIUM = 2
    HIGH = 3


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


class SargsUI:
    co2_measurement = None
    co2_level = CO2Level.MEDIUM
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
        CO2Level.HIGH: "AARGH!"
    }
    cal_sel_btn = 1
    main_screen_btn_handler = None
    cal_screen_btn_handler = None
    cal_screen_negedge_count = 0
    cal_screen_act_time = 0

    def __init__(self, screen, btn_signal):
        self.log = logging.getLogger("screen")
        self.screen = screen
        self.btn_signal = btn_signal
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

    def update(self):

        self.screen.fill(0)
        screen_fn_map = {
            ScreenState.MAIN_SCREEN: self.draw_main_screen,
            ScreenState.CALIBRATION_SCREEN: self.draw_calibration_screen,
        }
        if self.current_screen in screen_fn_map.keys():
            screen_fn_map[self.current_screen]()
        self.screen.show()

    def draw_main_screen(self):
        if self.main_screen_btn_handler.longpress():
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
                else:
                    # no btn selected, go back to main screen
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
