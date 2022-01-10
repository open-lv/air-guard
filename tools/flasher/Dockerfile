FROM python:3.10.1-slim-buster

ARG ESPTOOL_VERSION=3.2
ARG AMPY_VERSION=1.1.0

WORKDIR /build

RUN apt-get update; \
    apt-get --yes --no-install-recommends install curl screen

RUN pip3 install \
        esptool==$ESPTOOL_VERSION \
        adafruit-ampy==$AMPY_VERSION

CMD ["/usr/local/bin/esptool.py", "--help"]