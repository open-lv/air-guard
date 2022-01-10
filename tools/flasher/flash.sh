#!/bin/bash

# Uncomment this for verbose output.
# set -ex 

# esptool.py is required.
if ! command -v "esptool.py"; then
    echo "ERROR: esptool.py not found! See https://docs.espressif.com/projects/esptool/en/latest/esp32/installation.html"
    exit 1
fi

# Expect to have the UART path as the only arg.
UART_PATH="${1:-$UART_PATH}"
if [ -z "$UART_PATH" ]; then
	echo "Specify the path to the UART port (/dev/tty....) as the first argument."
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
    echo "Firmware file $FIRMWARE_FILE_NAME not found at the current directory $PWD."
    exit 1
fi

# First make sure the flash is empty.
esptool.py --port "$UART_PATH" erase_flash

# Now flash the MicroPython firmware.
esptool.py --chip esp32 --port "$UART_PATH" --baud 460800 write_flash -z 0x1000 "$FIRMWARE_FILE_NAME"

