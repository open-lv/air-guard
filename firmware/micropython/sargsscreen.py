import logging


# uPy doesn't seem to support enums, this is probably better than passing constants around


class WiFiState:
    UNCONFIGURED = 1
    CONNECTING = 2
    CONNECTED = 3


class CO2Level:
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class SargsScreenException(Exception):
    pass


class SargsScreen:
    co2_measurement = None
    co2_level = CO2Level.MEDIUM
    wifi_state = WiFiState.UNCONFIGURED
    WIFI_STATE_DESC = {WiFiState.UNCONFIGURED: "nav konf.",
                       WiFiState.CONNECTING: "savienojas",
                       WiFiState.CONNECTED: "savienots"
                       }

    def __init__(self, screen, btn_signal):
        self.log = logging.getLogger("screen")
        self.screen = screen
        self.btn_signal = btn_signal

    def set_co2_measurement(self, m):
        self.co2_measurement = m

    def set_wifi_state(self, s):
        self.wifi_state = s

    def set_co2_level(self, l):
        self.co2_level = l

    def update(self):
        self.screen.fill(0)

        if self.co2_measurement is None:
            self.screen.text("Sensors uzsilst", 0, 0, 1)
        else:
            self.screen.text("CO2: %d ppm" % self.co2_measurement, 0, 0, 1)

        # since user can change the threshold in main.py, use the state of output LEDs
        if self.co2_level == CO2Level.LOW:
            self.screen.text("LABS GAISS!", 0, 20, 2)
        elif self.co2_level == CO2Level.MEDIUM:
            self.screen.text("ATVER LOGU!", 0, 20, 2)
        elif self.co2_level == CO2Level.HIGH:
            self.screen.text("AARGH!", 0, 20, 2)

        if self.wifi_state not in self.WIFI_STATE_DESC.keys():
            raise SargsScreenException("Invalid WiFi state provided: %s" % str(self.wifi_state))

        self.screen.text("Wi-Fi: %s" % self.WIFI_STATE_DESC[self.wifi_state], 0, 30, 2)

        self.screen.show()
