from umqtt.simple import MQTTClient
import logging
from utime import ticks_ms


class AirGuardIotMQTTClient(MQTTClient):
    """Implements the Air Guard MQTT client API."""

    def __init__(self, username, password):
        self.log = logging.getLogger("mqtt_client")

        super().__init__(client_id=username,
                         server="mqtt.gaisasargs.lv",
                         user=username,
                         password=password)

        self.log.info("AirGuardIotMQTTClient initialized, server=%s, user=%s", self.server, self.user)

        self.publish_interval_s = 60
        self.next_publish_time_ms = 0

    def send_telemetry(self, payload):
        """Send JSON payload to the telemetry endpoint v1/devices/me/telemetry"""
        if ticks_ms() > self.next_publish_time_ms:
            self.next_publish_time_ms = ticks_ms() + self.publish_interval_s * 1000
            self.log.info("publishing sensor measurements payload: %s", payload)
            self.connect()
            self.publish("v1/devices/me/telemetry", payload)
            self.disconnect()
