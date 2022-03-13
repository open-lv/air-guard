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

# jq is required.
if ! [ -x "$(command -v "jq")" ]; then
  red "ERROR: jq not found! See https://stedolan.github.io/jq/"
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

  # Allow user to pick a port if multiple found.
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

    ESPTOOL_PORT="$(echo "$DEVICE_PORTS_LIST" | sed -n "$REPLY"p)"
    if [ -z "$ESPTOOL_PORT" ]; then
      red "Invalid device selected. Exiting"
      exit 1
    fi
  else
    # Select the first and only port detected.
    ESPTOOL_PORT="$(echo "$DEVICE_PORTS_LIST" | head -1)"
  fi
fi

# Make it available as an environment variable.
export ESPTOOL_PORT="$ESPTOOL_PORT"

green "Selected device to flash: $(echo "$DEVICE_LIST" | grep "$ESPTOOL_PORT")"

# Allow the firmware file path to be passed as the second argument to this script.
FIRMWARE_FILE_NAME="${2:-$FIRMWARE_FILE_NAME}"
if [ -z "$FIRMWARE_FILE_NAME" ]; then
  yellow "Firmware filename not supplied, auto-detecting..."
  RELEASES_JSON=$(curl -s https://api.github.com/repos/open-lv/micropython/releases/latest)
  LATEST_VERSION="$(echo "$RELEASES_JSON" | jq ".tag_name" | cut -d '"' -f 2)"
  LATEST_VERSION_DOWNLOAD_URL="$(echo "$RELEASES_JSON" | jq ".assets[] | select(.name==\"esp32-airguard-firmware.bin\") | .browser_download_url" | cut -d '"' -f 2)"
  FIRMWARE_FILE_NAME="esp32-airguard-firmware-${LATEST_VERSION}.bin"
fi

# Download the firmware if not found.
if [ ! -f "$FIRMWARE_FILE_NAME" ]; then
  yellow "Firmware binaries not found"
  yellow "Downloading latest firmware ${LATEST_VERSION}: https://github.com/open-lv/micropython/releases/latest"
  curl -L -s "$LATEST_VERSION_DOWNLOAD_URL" --output "$FIRMWARE_FILE_NAME"
fi

if [ ! -f "$FIRMWARE_FILE_NAME" ]; then
  echo "MicroPython firmware file $FIRMWARE_FILE_NAME not found at the current directory $PWD."
  exit 1
fi

green "Using firmware binary: $FIRMWARE_FILE_NAME"
# Collect build
./build.sh

if [ -f "../../firmware/micropython/config.json" ]; then
  yellow "Using preconfigured \"config.json\""
  cp ../../firmware/micropython/config.json build/
fi

cyan_underlined "Erasing ESP32 flash (1/5)"
esptool.py --chip esp32 erase_flash

cyan_underlined "Flashing micropython firmware (2/5)"
esptool.py --chip esp32 --baud 460800 write_flash -z 0x1000 "$FIRMWARE_FILE_NAME"

cyan_underlined "Waiting for device to boot (3/5)"
RETRIES=0
while true; do
  mpremote connect "port:$ESPTOOL_PORT" exec "print('Device ready')" &>/dev/null && break
  RETRIES=$((+1))
  if [ "$RETRIES" -ge 5 ]; then
    red "Failed to boot device - disconnect and try again."
    red "Exiting"
    exit 1
  fi
done

cyan_underlined "Copying scripts to device (4/5)"
pushd build
mpremote connect "port:$ESPTOOL_PORT" cp -r . :
popd

# Keep the meta of all devices flashed
cyan_underlined "Registering device information (5/5)"
# carriage return needs to be trimmed
DEVINFO=`mpremote connect "port:$ESPTOOL_PORT" run ./register-device.py | sed "s/\r$//"`
echo "$DEVINFO,$FIRMWARE_FILE_NAME,$AIRGUARD_VERSION" >> devices-flashed.txt

esptool.py run
SCRIPT_END="$(date +%s)"

echo
green "Device flashing is done. It took $((SCRIPT_END - SCRIPT_START)) seconds to finish."
