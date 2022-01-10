# Air Guard ESP32 Flasher

See [`flash.sh`](./flash.sh) which flashes the core MicroPython firmware and the Air Guard script files. Run it on your local machine if you have both `esptool.py` and `ampy` installed or use the included Docker environment.

## Flashing Using Docker

Run `docker-compose build` to build the Docker container with the appropriate version of `esptool.py` and `ampy`.

Run `ESPTOOL_PORT=/dev/portName docker-compose run flash` to flash the firmware where `/dev/portName` is the absolute path to the UART port. Alternatively, use the `.env` file to set the `ESPTOOL_PORT` environment variable which will be picked up by `docker-compose` automatically.
