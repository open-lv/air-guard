import _thread
import os
import sys
import time
import uasyncio
import http_utils
import usocket
import logging

log = logging.getLogger("ota_utils")

STATUS_CANCELLED = "CANCELLED"
STATUS_FAILED = "FAILED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_FINISHED = "FINISHED"

gaisasargs_resolver = None
gaisasargs_addr_info = None

def print_ota_logs():
    try:
        with open("_ota_logs") as f:
            while True:
                line = f.readline()
                if not line:
                    break
                log.info(line.rstrip())
    except:
        log.info("OTA logs not found")


# rm -rf
def rmrf(d):
    if os.stat(d)[0] & 0x4000:  # Dir
        for f in os.ilistdir(d):
            if f[0] not in ('.', '..'):
                rmrf("/".join((d, f[0])))  # File or Dir
        os.rmdir(d)
    else:  # File
        os.remove(d)


def restore_original():
    with open("main.py", "w") as f:
        f.write("import original.main\n")
        f.write("original.main.run()\n")


def remove_all_versions():
    for dir_name in os.listdir():
        if dir_name.startswith("micropython_"):
            log.info("Removing version directory: %s" % dir_name)
            rmrf(dir_name)


async def check_update():
    global gaisasargs_addr_info

    if not gaisasargs_addr_info:
        log.error("gaisasargs.lv not resolved")
        return None

    reader = None
    try:
        reader = http_utils.open_url("https://gaisasargs.lv/latest_release", gaisasargs_addr_info[0])
        await uasyncio.sleep_ms(0)
        line = reader.read(24).splitlines()[0]
        reader.close()
        await uasyncio.sleep_ms(0)

        latest_version = line.decode('latin1').rstrip()

        if not latest_version.startswith("micropython-"):
            raise Exception("Invalid version response: %s" % latest_version)

        return latest_version[12:]
    except Exception as e:
        log.exc(e, "Error while checking \"https://gaisasargs.lv/latest_release\" update")
    finally:
        if reader:
            reader.close()

    return None

def gaisa_sargs_resolver_task():
    global gaisasargs_addr_info
    while True:
        log.debug("Resolving gaisasargs.lv")
        try:
            gaisasargs_addr_info = usocket.getaddrinfo("gaisasargs.lv", 443)[0][-1]
        except Exception as e:
            log.debug("Error resolving \"gaisasargs.lv\": %s" % str(e))
            gaisasargs_addr_info = None
        time.sleep(60)


def start_gaisasargs_resolver():
    # usocket.getaddrinfo is a blocking function
    global gaisasargs_resolver
    if gaisasargs_resolver:
        raise Exception("Resolver already started")
    gaisasargs_resolver = _thread.start_new_thread(gaisa_sargs_resolver_task, ())
    log.info("Started \"gaisasargs.lv\" DNS resolver")
