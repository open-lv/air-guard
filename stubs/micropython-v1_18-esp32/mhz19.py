import logging
import uasyncio
import ubinascii
import utime


class MHZ19Exception(Exception):
    pass


class MHZ19ChecksumException(MHZ19Exception):
    pass


class MHZ19InvalidResponseException(MHZ19Exception):
    pass


def calc_checksum(data):
    csum = 0
    for b in data:
        csum = (csum + b) % 256
    return (0xff - csum + 1) % 256


class MHZ19Cmd:
    body = bytearray()
    cmd = 0
    payload = bytearray()
    csum = 0

    def __init__(self, cmd, payload=None):
        """Creates a serialized 8-byte command from command byte and payload"""
        if cmd:
            self.cmd = bytearray([cmd])
        else:
            self.cmd = bytearray([0])
        if payload:
            assert (len(payload) == 5)
            self.payload = payload
        else:
            self.payload = bytearray([0] * 5)

        if cmd:
            self.pack()

    def pack(self):
        self.body = bytearray([0xff, 0x01]) + self.cmd + self.payload
        self.csum = calc_checksum(self.body[1:8])
        self.body += bytearray([self.csum, ])
        return self.body

    def unpack(self, resp):
        if len(resp) < 9:
            raise MHZ19InvalidResponseException("Expected 9 byte response, got %d bytes" % len(resp))

        self.body = resp
        self.cmd = resp[1]
        self.payload = resp[2:8]
        self.csum = resp[8]
        calc_csum = calc_checksum(self.body[1:8])
        if calc_csum != self.csum:
            raise MHZ19ChecksumException("Invalid checksum: received 0x%x, expected 0x%x (packet: %s)" % (
                self.csum, calc_csum, ubinascii.hexlify(self.body, " ")))


class MHZ19:
    CMD_GET_FW_VERSION = 0xA0
    CMD_GET_READING = 0x86
    CMD_SET_ABC_STATE = 0x79

    uart = None

    sensor_warmed_up = False
    prev_co2_reading = None
    cached_co2_reading = None
    cached_temperature_reading = None

    MIN_WARMUP_TIME_MS = 10 * 1000  # minimum sensor warmup time
    init_time = 0

    def __init__(self, uart):
        self.uart = uart
        self.swriter = uasyncio.StreamWriter(self.uart, {})
        self.sreader = uasyncio.StreamReader(self.uart)
        self.log = logging.getLogger("mhz19")
        self.init_time = utime.ticks_ms()
        self.log.info("initialized")

    async def send_cmd(self, cmd, payload=None):
        c = MHZ19Cmd(cmd, payload)
        c.pack()
        self.log.debug("Writing cmd: %s" % ubinascii.hexlify(c.body, " "))
        await self.swriter.awrite(c.body)
        resp = await self.sreader.read(9)
        if resp:
            c.unpack(resp)
            self.log.debug("Received cmd: %s" % ubinascii.hexlify(c.body, " "))

            return c

    async def verify(self):
        """Verifies connection to sensor, logs firmware version"""

        resp = await self.send_cmd(self.CMD_GET_FW_VERSION)
        if resp:
            self.log.info("MHZ19 detected")
            self.log.info("FW version: %d%d.%d%d" % tuple(resp.payload[:4]))
            return True
        else:
            self.log.error("could not read fw version")
            return False

    async def get_co2_reading(self):
        resp = await self.send_cmd(self.CMD_GET_READING)
        if resp:
            # decode the reading
            # payload format: HH LL TT SS U1 U2
            # HH LL: CO2 measurement (2-bytes)
            # TT: temperature, supposedly
            # SS: status
            # U1 U2 unknown value
            # proposed heuristic by https://revspace.nl/MHZ19 (status 0x40, U1U2 < 15000 doesn't seem to work on C
            # sensor (ss, u1, u2 are always 0)
            # so, the current best guess is to wait for the sensor to start returning a different co2 value than it
            # was reporting previously

            reading_ppm = resp.payload[0] << 8 | resp.payload[1]
            status = resp.payload[3]
            unknown_value = resp.payload[4] | resp.payload[5]
            temperature = resp.payload[2] - 40  # offset of 40 seems to work for C sensor
            self.log.info("reading: %dppm, temp=%d, status=0x%x, unknown value=%d" %
                          (reading_ppm, temperature, status, unknown_value))

            min_warmup_done = (utime.ticks_ms() - self.init_time) > self.MIN_WARMUP_TIME_MS

            if min_warmup_done:

                if self.prev_co2_reading and reading_ppm != self.prev_co2_reading and not self.sensor_warmed_up:
                    self.log.info("sensor warmup detected")
                    self.sensor_warmed_up = True
                self.prev_co2_reading = reading_ppm

            if self.sensor_warmed_up:
                self.cached_co2_reading = reading_ppm
                self.cached_temperature_reading = temperature
                return reading_ppm
            else:
                return None
        else:
            return None

    async def set_abc_state(self, abc_state):
        """Turns the automatic baseline calibration on/off"""
        payload = bytearray([0] * 5)
        if abc_state:
            payload[0] = 0xA0
        resp = await self.send_cmd(self.CMD_SET_ABC_STATE, payload)
        if resp and resp.payload[0] != 0x1:
            self.log.error("failed to set ABC state to %d" % abc_state)
            return False
        if resp is None:
            self.log.warning("no response for set ABC state")
        else:
            self.log.info("successfully set ABC state to %d" % abc_state)
        return True

    def get_cached_co2_reading(self):
        return self.cached_co2_reading

    def get_cached_temperature_reading(self):
        return self.cached_temperature_reading


class MHZ19Sim(MHZ19):
    """Simulated MHZ19 sensor- replaces the send_cmd method with one which returns pre-defined responses"""

    # responses contains response data
    # checksum is re-calculated before responding
    RESPONSES = {
        MHZ19.CMD_GET_FW_VERSION: bytearray([0xff, MHZ19.CMD_GET_FW_VERSION, 0, 5, 0, 0, 0, 0]),
        MHZ19.CMD_GET_READING: bytearray([0xff, MHZ19.CMD_GET_READING, 0x1, 0xa4, 0, 0, 0, 0]),
    }

    def send_cmd(self, cmd, payload=None):
        c = MHZ19Cmd(cmd, payload)
        c.pack()
        self.log.debug("Processing simulated cmd: %s" % ubinascii.hexlify(c.body, " "))

        if cmd in self.RESPONSES.keys():
            c.unpack(self.RESPONSES[cmd])
            c.body[7] = calc_checksum(c.body[1:7])
            self.log.debug("Returning simulated response: %s" % ubinascii.hexlify(c.body, " "))
            return c

    def set_sim_co2(self, co2_ppm):
        self.RESPONSES[MHZ19.CMD_GET_READING][2] = (co2_ppm >> 8) & 0xff
        self.RESPONSES[MHZ19.CMD_GET_READING][3] = co2_ppm & 0xff
