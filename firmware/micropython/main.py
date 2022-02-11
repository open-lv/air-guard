import uasyncio
from sargs import *
import portal

log = logging.getLogger("main")


async def measurements():
    while True:
        measurement = await perform_co2_measurement()
        sargs.handle_co2_measurement(measurement)

        if measurement <= 1000:
            sargs.led_yellow.off()
            sargs.led_red.off()

            sargs.led_green.on()
        elif measurement <= 1400:
            sargs.led_green.off()
            sargs.led_red.off()

            sargs.led_yellow.on()
        elif measurement > 1400:
            sargs.led_green.off()
            sargs.led_yellow.off()

            sargs.led_red.on()

        await uasyncio.sleep(5)


async def setup():
    log.info("Setting up Sargs")
    await sargs.setup()

    log.info("Animating Screen and LEDs")
    # Ekrāna pārbaude
    sargs.screen.drawText(20, 21, 'Sveika, pasaule!')
    sargs.screen.flush()

    # Pārbaude pēc ieslēgšanās: ieslēdzam visas gaismas diodes pēc kārtas un pēc tam izslēdzam tās
    pins = [sargs.led_green, sargs.led_yellow, sargs.led_red, sargs.led_right_eye, sargs.led_left_eye]
    for p in pins:
        p.on()
        await uasyncio.sleep(0.25)
    await uasyncio.sleep(1)
    for p in reversed(pins):
        p.off()
        await uasyncio.sleep(0.25)

    log.info("Setting up tasks")
    portal.setup()
    uasyncio.create_task(sargs.run())
    await measurements()


try:
    uasyncio.run(setup())
except KeyboardInterrupt:
    event_loop = uasyncio.get_event_loop()
    event_loop.close()
