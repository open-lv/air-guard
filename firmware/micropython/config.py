import logging

import ujson
import os


class SargsConfig:
    logger = logging.getLogger("config")

    # To enable WiFi connection, fill in the WiFi network details below
    WIFI_ENABLED = True
    WIFI_SSID = ""
    WIFI_PASSWORD = ""

    # To enable Captive portal
    CAPTIVE_PORTAL_ENABLED = True

    _json_mapping = {
        # JSON field, Class attribute, type
        "WIFI_ENABLED": ("wifiEnabled", bool),
        "WIFI_SSID": ("wifiSsid", str),
        "WIFI_PASSWORD": ("wifiPassword", str),
        "CAPTIVE_PORTAL_ENABLED": ("captivePortalEnabled", bool),
    }

    def __setattr__(self, name, value) -> None:
        if name not in self._json_mapping:
            raise Exception('Invalid configuration key "%s"' % name)

        (config_field, config_type) = self._json_mapping[name]
        if value is not None and not isinstance(value, config_type):
            raise Exception('Invalid configuration value for "%s", must be of type "%s"' % (name, config_type.__name__))

        super().__setattr__(name, value)

    def save(self):
        try:
            with open("config.json") as config_file:
                config_json = ujson.load(config_file)
        except:
            self.logger.info("config.json doesn't exist")
            config_json = {}

        for global_name in self._json_mapping:
            (config_field, config_type) = self._json_mapping[global_name]
            config_json[config_field] = getattr(self, global_name)

        with open("config.json", "w") as config_file:
            ujson.dump(config_json, config_file)

        self.logger.info("config.json written successfully!")

    def __init__(self):
        try:
            os.stat("config.json")
        except:
            self.logger.warning("config.json does not exist")
            return

        with open("config.json") as config_file:
            config_json = ujson.load(config_file)

        for global_name in self._json_mapping:
            (config_field, config_type) = self._json_mapping[global_name]
            if config_field not in config_json:
                continue
            setattr(self, global_name, config_json[config_field])


sargsConfig = SargsConfig()
