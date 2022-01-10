FROM python:3.10.1-slim-buster

ARG ESPTOOL_VERSION=3.2

WORKDIR /build

RUN apt-get update; \
    apt-get --yes --no-install-recommends install curl screen

RUN pip3 install esptool==${ESPTOOL_VERSION}

CMD ["/usr/local/bin/esptool.py", "--help"]