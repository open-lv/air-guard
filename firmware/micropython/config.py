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

    # MQTT common configuration
    MQTT_CLIENT_ID = ""
    MQTT_USERNAME = MQTT_CLIENT_ID
    MQTT_PASSWORD = ""

    # interval between published messages, seconds
    MQTT_PUBLISH_INTERVAL_S = 60

    # Thingspeak channel id
    MQTT_TS_CHANNEL = ""

    # Select which MQTT implementation to use
    # Currently implemented: ThingspeakMQTTClient, requires MQTT_TS_CHANNEL
    MQTT_CLASS = "ThingspeakMQTTClient"

    _json_mapping = [
        # JSON field, Class attribute, type
        ("wifiEnabled", "WIFI_ENABLED", bool),
        ("wifiSsid", "WIFI_SSID", str),
        ("wifiPassword", "WIFI_PASSWORD", str),
        ("captivePortalEnabled", "CAPTIVE_PORTAL_ENABLED", bool),
        ("mqttClientId", "MQTT_CLIENT_ID", str),
        ("mqttUsername", "MQTT_USERNAME", str),
        ("mqttPassword", "MQTT_PASSWORD", str),
        ("mqttPublishIntervalS", "MQTT_PUBLISH_INTERVAL_S", int),
        ("mqttTsChannel", "MQTT_TS_CHANNEL", str),
        ("mqttClass", "MQTT_CLASS", str),
    ]

    def save(self):
        pass

    def __init__(self):
        try:
            os.stat("config.json")
        except:
            self.logger.warning("config.json does not exist")
            return

        with open("config.json") as config_file:
            config_json = ujson.load(config_file)

        for json_attr in self._json_mapping:
            (config_field, global_name, config_type) = json_attr
            if config_field not in config_json:
                continue
            if not isinstance(config_json[config_field], config_type):
                raise Exception('Configuration "%s" must be of type "%s"' % (config_field, config_type.__name__))
            setattr(self, global_name, config_json[config_field])


sargsConfig = SargsConfig()
