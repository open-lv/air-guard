FROM python:3.10.1-slim-buster

WORKDIR /build

RUN apt-get update; \
    apt-get --yes --no-install-recommends install curl

COPY requirements.txt /tmp/flasher-requirements.txt

RUN pip3 install -r /tmp/flasher-requirements.txt

CMD ["/usr/local/bin/esptool.py", "--help"]