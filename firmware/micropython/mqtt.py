from umqtt.simple import MQTTClient
import logging
from utime import ticks_ms


class ThingspeakMQTTClient(MQTTClient):
    """ Implements MQTT client that knows about thingspeak (server, topic and payload format) """

    def __init__(self, config):
        self.log = logging.getLogger("tsmqtt")

        super().__init__(client_id=config.MQTT_CLIENT_ID, server="mqtt3.thingspeak.com",
                         user=config.MQTT_USERNAME, password=config.MQTT_PASSWORD)

        self.log.info("thingspeak mqtt client initialized, server=%s, client_id=%s, user=%s" % (
        self.server, self.client_id, self.user))
        self.topic = "channels/" + config.MQTT_TS_CHANNEL + "/publish"
        self.log.debug("mqtt topic: %s" % self.topic)

        self.publish_interval_s = getattr(config, "MQTT_PUBLISH_INTERVAL_S", 60)
        self.next_publish_time_ms = 0

    def handle_co2_measurement(self, co2_measurement, temperature_measurement=None):
        if ticks_ms() > self.next_publish_time_ms:
            self.next_publish_time_ms = ticks_ms() + self.publish_interval_s * 1000
            payload = "field1=%d" % co2_measurement
            if temperature_measurement:
                payload += "&field2=%d" % temperature_measurement
            self.log.info("publishing mqtt topic %s, payload: %s" % (self.topic, payload))
            self.connect()
            self.publish(self.topic, payload)
            self.disconnect()
