import logging
import ubinascii

class MHZ19Exception(Exception):
    pass

class MHZ19ChecksumException(MHZ19Exception):
    pass

class MHZ19InvalidResponseException(MHZ19Exception):
    pass

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
      assert(len(payload) == 5)
      self.payload = payload
    else:
      self.payload = bytearray([0] * 5)

    if cmd:
      self.pack()

  def calc_checksum(self, data):
    csum = 0
    for b in self.body[1:8]:
      csum = (csum + b) % 256
    return (0xff - csum + 1) % 256


  def pack(self):
    self.body = bytearray([0xff, 0x01]) + self.cmd + self.payload
    self.csum = self.calc_checksum(self.body[1:7])
    self.body += bytearray([self.csum, ])
    return self.body

  def unpack(self, resp):
    if len(resp) < 9:
        raise MHZ19InvalidResponseException("Expected 9 byte response, got %d bytes" % len(resp))
    
    self.body = resp
    self.cmd = resp[1]
    self.payload = resp[2:7]
    self.csum = resp[8]
    calc_csum = self.calc_checksum(self.body)
    if calc_csum != self.csum:
        raise MHZ19ChecksumException("Invalid checksum: received 0x%x, expected 0x%x (packet: %s)" % (self.csum, calc_csum, ubinascii.hexlify(self.body, " ")))


class MHZ19:
  CMD_GET_FW_VERSION = 0xA0
  CMD_GET_READING = 0x86

  uart = None
  def __init__(self, uart):
    self.uart = uart
    self.log = logging.getLogger("mhz19")
    self.log.setLevel(logging.DEBUG)
    self.log.info("initialized")
    self.verify()

  def send_cmd(self, cmd, payload=None):
    c = MHZ19Cmd(cmd, payload)
    c.pack()
    self.log.debug("Writing cmd: %s" % ubinascii.hexlify(c.body, " "))
    self.uart.write(c.body)
    resp = self.uart.read(9)
    if resp:
      c.unpack(resp)
      self.log.debug("Received cmd: %s" % ubinascii.hexlify(c.body, " "))

      return c


  def verify(self):
    """Verifies connection to sensor, logs firmware version"""
    
    resp = self.send_cmd(self.CMD_GET_FW_VERSION)
    if resp:
      self.log.info("MHZ19 detected")
      self.log.info("FW version: %d%d.%d%d" % tuple(resp.payload[:4]))
      return True
    else:
      self.log.error("could not read fw version")
      return False

  def get_co2_reading(self):
    resp = self.send_cmd(self.CMD_GET_READING)
    if resp:
      reading_ppm = resp.payload[0] << 8 | resp.payload[1]
      return reading_ppm
    else:
      return None


class MHZ19Sim(MHZ19):
  """Simulated MHZ19 sensor- replaces the send_cmd method with one which returns pre-defined responses"""

  # responses contains response data
  # checksum is re-calculated before responding
  RESPONSES = {
    MHZ19.CMD_GET_FW_VERSION : bytearray([0xff, MHZ19.CMD_GET_FW_VERSION, 0, 5, 0, 0, 0, 0]),
    MHZ19.CMD_GET_READING : bytearray([0xff, MHZ19.CMD_GET_READING, 0x1, 0xa4, 0, 0, 0, 0]),
  }

  def send_cmd(self, cmd, payload=None):
    c = MHZ19Cmd(cmd, payload)
    c.pack()
    self.log.debug("Processing simulated cmd: %s" % ubinascii.hexlify(c.body, " "))

    if cmd in self.RESPONSES.keys():
      c.unpack(self.RESPONSES[cmd])
      c.body[7] = c.calc_checksum(c.body[1:7])
      self.log.debug("Returning simulated response: %s" % ubinascii.hexlify(c.body, " "))
      return c
  
  def set_sim_co2(self, co2_ppm):
    self.RESPONSES[MHZ19.CMD_GET_READING][2] = (co2_ppm >> 8) & 0xff
    self.RESPONSES[MHZ19.CMD_GET_READING][3] = co2_ppm & 0xff
    



    

