import os
import ota_utils
import machine
import time
import utime

btn_arm = machine.Signal(machine.Pin(35, machine.Pin.IN, machine.Pin.PULL_UP), invert=True)

buzzer = machine.PWM(machine.Pin(32))
buzzer.init(freq=1000, duty=0)


def wait_button(stages_count, stages=()):
    if btn_arm.value():
        print("Reset stage: %d" % len(stages))
        ticks_on_pressed = utime.ticks_ms()

        while True:
            if not btn_arm.value():
                break
            if (utime.ticks_ms() - ticks_on_pressed) > 5000:

                buzzer.duty(512)
                utime.sleep_ms(500)
                buzzer.duty(0)
                stages = stages + (True,)
                if len(stages) == stages_count:
                    break
                return wait_button(stages_count, stages)
            time.sleep_ms(10)

    for missing_stages in range(stages_count - len(stages)):
        stages = stages + (False,)

    return stages


(is_recover_old_version, is_remove_other_versions, _, is_full_reset) = wait_button(4)

if is_recover_old_version:
    print("Restoring original version")
    ota_utils.restore_original()

if is_remove_other_versions:
    print("Removing other version")
    ota_tools.remove_all_versions()

if is_full_reset:
    print("Removing all data")
    os.remove("_ota_logs")
    os.remove("_ota_status")
    os.remove("config.json")

if is_recover_old_version:
    machine.reset()

buzzer.deinit()

directories = os.listdir()
if "original" in directories:
    print("Warning: \"Original\" directory detected, original firmware might be shadowed")

try:
    with open("_ota_status", "r") as f:
        status = f.read()
        print("Last OTA status: %s" % status)
        if status == ota_utils.STATUS_FAILED:
            print("OTA logs latest messages:")
            ota_utils.print_ota_logs()
        print("\n\n")
except:
    pass

try:
    with open("main.py", "r") as f:
        pass
except Exception as e:
    print("\"main.py\" not detected, restoring to original")
    ota_utils.restore_original()
    machine.reset()
