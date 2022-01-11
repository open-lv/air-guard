MicroPython version of air-guard firmware
--------------------------------------------

The firmware is quite basic at the moment:

  * MHZ19C readings are performed as per datasheet. It appears that during heating phase, it returns a value of 500 (which is misleading and should not be presented to user)
  * main.py intentionally contains the "main" logic, while everything else is hidden under sargs.py. A separate thread is started when importing sargs.py which will handle all the 
  background functionality (re-drawing the screen, connecting to WiFi, publishing readings over MQTT etc)
  * There is comprehensive logging to serial console- do check the console output if something is not working as expected


Startup error conditions
-------------------

  * Blinking red LED: I2C OLED not responding
  * Blinking yellow LED: CO2 sensor not responding


Configuration
----------------------

To enable WiFi functionality, copy the config.py.example file to config.py and enter the configuration details in the file.

To enable publishing to ThingSpeak channel, fill in the following configuration in config.py:
    
  * MQTT_CLIENT_ID = "ThingSpeak client ID"
  * MQTT_PASSWORD = "ThingSpeak MQTT device password"
  * MQTT_TS_CHANNEL = "ThingSpeak channel ID"
  * MQTT_CLASS = "ThingspeakMQTTClient"

CO2 sensor calibration
--------------------------

Manually triggered 400ppm point calibration is implemented. To use it, make sure the sensor is exposed
to ~400ppm (fresh air, outside) for at least 20 minutes before and after starting the calibration.

To start calibration, press the button for at least 5 seconds, then select "Yes" button on confirmation dialog with a short press,
then confirm the start of calibration by long press when "Yes" button is selected.

MicroPython version
-------------------------

This firmware is developed against MicroPython for ESP32 v1.17.

