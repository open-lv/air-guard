import uasyncio
from sargs import *
import portal

# Ekr膩na p膩rbaude
SCREEN.text('Sveika, pasaule!', 0, 0, 1)
SCREEN.show()

# P膩rbaude p膿c iesl膿g拧an膩s: iesl膿dzam visas gaismas diodes p膿c k膩rtas un p膿c tam izsl膿dzam t膩s
pins = [LED_GREEN, LED_YELLOW, LED_RED, LED_RIGHT_EYE, LED_LEFT_EYE]
for p in pins:
    p.on()
    sleep(0.25)
sleep(1)
for p in reversed(pins):
    p.off()
    sleep(0.25)


async def measurements():
    while True:
        measurement = perform_co2_measurement()
        handle_co2_measurement(measurement)

        if measurement <= 1000:
            LED_YELLOW.off()
            LED_RED.off()

            LED_GREEN.on()
        elif measurement <= 1400:
            LED_GREEN.off()
            LED_RED.off()

            LED_YELLOW.on()
        elif measurement > 1400:
            LED_GREEN.off()
            LED_YELLOW.off()

            LED_RED.on()

        await uasyncio.sleep(5)

event_loop = uasyncio.get_event_loop()
event_loop.create_task(measurements())
portal.setup()

try:
    event_loop.run_forever()
except KeyboardInterrupt:
    event_loop.close()
