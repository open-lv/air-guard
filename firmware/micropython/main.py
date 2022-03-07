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


def set_global_exception():
    def handle_exception(loop, context):
        import sys
        sys.print_exception("Unhandled exception in async function: %s" % context["exception"])
        sys.exit()

    loop = uasyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)


async def setup():
    import gc
    log.info("mem_free=%d" % gc.mem_free())
    log.info("Setting up Sargs")

    set_global_exception()  # Debug aid

    await sargs.setup()

    log.info("mem_free=%d" % gc.mem_free())
    log.info("Animating Screen and LEDs")
    # Ekrāna pārbaude
    await sargs.draw_centered_text(21, 'GAISA SARGS')
    await sargs.draw_centered_text(32, 'VERSIJA ' + sargs.version[0:8])
    sargs.screen.flush()

    log.info("mem_free=%d" % gc.mem_free())
    # Pārbaude pēc ieslēgšanās: ieslēdzam visas gaismas diodes pēc kārtas un pēc tam izslēdzam tās
    pins = [sargs.led_green, sargs.led_yellow, sargs.led_red, sargs.led_right_eye, sargs.led_left_eye]
    for p in pins:
        p.on()
        await uasyncio.sleep(0.25)
    await uasyncio.sleep(1)
    for p in reversed(pins):
        p.off()
        await uasyncio.sleep(0.25)

    log.info("mem_free=%d" % gc.mem_free())
    log.info("Setting up tasks")
    portal.setup()
    uasyncio.create_task(sargs.run())

    log.info("mem_free=%d" % gc.mem_free())
    await measurements()


try:
    uasyncio.run(setup())
except KeyboardInterrupt:
    event_loop = uasyncio.get_event_loop()
    event_loop.close()
