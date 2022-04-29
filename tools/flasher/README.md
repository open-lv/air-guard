# Air Guard ESP32 Flasher

See [`flash.sh`](./flash.sh) which flashes the core MicroPython firmware and the Air Guard script files. Run it on your local machine if you have `esptool.py`, `ampy` and 'jq' installed or use the included Docker environment. If needed, use brew to add what's missing to your local environment (e.g. 'brew install jq'). 

## Flashing Locally

Install the required Python packages defined in [requirements.txt](./requirements.txt):

    pip install -r requirements.txt

Note that you might need to replace `pip` with `pip3` in the command above depending on your operating system.

Now run the flashing tool which will automatically download the required version of MicroPython firmware, flash it to the device and upload all `*.py` files from the `firmware/micropyhton` directory to the device:

    ESPTOOL_PORT=/dev/tty.usbserial ./flash.sh

where `ESPTOOL_PORT` is the environment variable pointing to the UART port path `/dev/tty.usbserial` with the ESP32 device attached.

## Flashing Using Docker

Note that mounting USB ports inside Docker containers is only supported on Linux host computers. Docker on MacOS and Windows doesn't support this.

Run `docker-compose build` to build the Docker container with the appropriate version of `esptool.py` and `ampy`.

Run `ESPTOOL_PORT=/dev/tty.usbserial docker-compose run --rm flash` to flash the firmware where `/dev/tty.usbserial` is the UART device port path. Alternatively, use the `.env` file to set the `ESPTOOL_PORT` environment variable which will be picked up by `docker-compose` automatically.
