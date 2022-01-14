from sargs import *

# Ekrāna pārbaude
SCREEN.text('Sveika, pasaule!', 0, 0, 1)
SCREEN.show()

# Pārbaude pēc ieslēgšanās: ieslēdzam visas gaismas diodes pēc kārtas un pēc tam izslēdzam tās
pins = [LED_GREEN, LED_YELLOW, LED_RED, LED_RIGHT_EYE, LED_LEFT_EYE]
for p in pins:
    p.on()
    sleep(0.25)
sleep(1)
for p in reversed(pins):
    p.off()
    sleep(0.25)


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

    sleep(5)
