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
