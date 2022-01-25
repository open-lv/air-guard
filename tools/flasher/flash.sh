#!/bin/bash

SCRIPT_START="$(date +%s)"

set -e
. colors.sh

# Uncomment this for verbose output.
# set -x

# esptool.py is required.
if ! [ -x "$(command -v "esptool.py")" ]; then
  red "ERROR: esptool.py not found! See https://pypi.org/project/esptool/"
  exit 1
fi

# mpremote is required.
if ! [ -x "$(command -v "mpremote")" ]; then
  red "ERROR: mpremote not found! See https://pypi.org/project/mpremote/"
  exit 1
fi

DEVICE_LIST="$(mpremote connect list)"

if [ -z "$DEVICE_LIST" ]; then
  red "No suitable device found. Exiting"
  exit 1
fi

DEVICE_PORTS_LIST="$(echo "$DEVICE_LIST" | cut -d' ' -f1)"

if [ -n "$ESPTOOL_PORT" ]; then
  if ! echo "$DEVICE_PORTS_LIST" | grep -x -q "$ESPTOOL_PORT"; then
    red "Invalid $ESPTOOL_PORT device port"
    red "Suitable devices: "
    red "$DEVICE_LIST"
    red "Exiting"
    exit 1
  fi
else
  yellow "ESPTOOL_PORT empty, auto-detecting device port..."

  if [ "$(echo "$DEVICE_LIST" | wc -l)" -gt "1" ]; then
    yellow "Found more than single serial device."
    echo
    echo "$DEVICE_LIST" | nl -w2 -s'> ' | sed "s/^.*>/$(green "&")/"
    read -p "$(green "Select the device: ")" -r
    echo
    if ! [ "$REPLY" -eq "$REPLY" ]; then
      echo "Exiting.."
      exit 1
    fi

    SELECTED_DEVICE="$(echo "$DEVICE_LIST" | sed -n "$REPLY"p)"
    if [ -z "$SELECTED_DEVICE" ]; then
      red "Invalid device selected. Exiting"
      exit 1
    fi
  else
    ESPTOOL_PORT="$(echo "$DEVICE_PORTS_LIST" | head -1)"
  fi
fi

green "Selected device to flash: $(echo "$DEVICE_LIST" | grep "$ESPTOOL_PORT")"

# Specify the MicroPython firmware source.
FIRMWARE_URL="https://micropython.org/resources/firmware/esp32-20220117-v1.18.bin"

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

# Collect build
[ ! -d "build" ] && mkdir build
# -f to ignore empty build dir
rm -r build/*
cp ../../firmware/micropython/*.py build/

cyan_underlined "Erasing ESP32 flash (1/5)"
esptool.py --chip esp32 erase_flash

cyan_underlined "Flashing micropython firmware (2/5)"
esptool.py --chip esp32 --baud 460800 write_flash -z 0x1000 "$FIRMWARE_FILE_NAME"

cyan_underlined "Waiting for device to boot (3/5)"
RETRIES=0
while true; do
  mpremote exec "print('Device ready')" &>/dev/null && break
  RETRIES=$((+1))
  if [ "$RETRIES" -ge 5 ]; then
    red "Failed to boot device - disconnect and try again."
    red "Exiting"
    exit 1
  fi
done

cyan_underlined "Copying scripts to device (4/5)"
pushd build
mpremote cp -r . :
popd

# Keep the meta of all devices flashed
cyan_underlined "Registering device information (5/5)"
mpremote run ./register-device.py >devices-flashed.txt

SCRIPT_END="$(date +%s)"

echo
green "Device flashing is done. It took $((SCRIPT_END - SCRIPT_START)) seconds to finish."
