#!/bin/bash

# Uncomment this for verbose output.
# set -ex 

# esptool.py is required.
if [ ! command -v "esptool.py" &> /dev/null ]; then
    echo "ERROR: esptool.py not found! See https://pypi.org/project/esptool/"
    exit 1
fi

# ampy is required.
if [ ! command -v "ampy" &> /dev/null ]; then
    echo "ERROR: ampy not found! See https://pypi.org/project/adafruit-ampy/"
    exit 1
fi

# Expect to have the UART path as the only arg.
if [ -z "$ESPTOOL_PORT" ]; then
	echo "Specify configure the ESPTOOL_PORT environment variable to point to the UART port (/dev/tty...)."
	exit 1
fi

# Specify the MicroPython firmware source. 
FIRMWARE_URL="https://micropython.org/resources/firmware/esp32-20210902-v1.17.bin"

# Allow the firmware file path to be passed as the second argument to this script.
FIRMWARE_FILE_NAME="${2:-$FIRMWARE_FILE_NAME}"
if [ -z "$FIRMWARE_FILE_NAME" ]; then
    FIRMWARE_FILE_NAME="${FIRMWARE_URL##*/}"
fi

# Download the firmware if not found.
if [ ! -f "$FIRMWARE_FILE_NAME" ]; then
    curl --remote-name --location "$FIRMWARE_URL"
fi

if [ ! -f "$FIRMWARE_FILE_NAME" ]; then
    echo "MicroPython firmware file $FIRMWARE_FILE_NAME not found at the current directory $PWD."
    exit 1
fi

# First make sure the flash is empty.
esptool.py erase_flash

# Now flash the MicroPython firmware.
esptool.py --chip esp32 --baud 460800 write_flash -z 0x1000 "$FIRMWARE_FILE_NAME"

# Now upload our own firmware.
ampy --port "$ESPTOOL_PORT" put ../../firmware/micropython/
ampy --port "$ESPTOOL_PORT" ls

# Keep the meta of all devices flashed
ampy --port "$ESPTOOL_PORT" run ./register-device.py > devices-flashed.txt