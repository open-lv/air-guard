import gc
import logging
import uasyncio
import uasyncio.core
import usocket as socket

log = logging.getLogger('captive_dns')


class DNSQuery:
    def __init__(self, data):
        self.data = data
        self.domain = ""
        # header is bytes 0-11, so question starts on byte 12
        head = 12
        # length of this label defined in first byte
        length = data[head]
        while length != 0:
            label = head + 1
            # add the label to the requested domain and insert a dot after
            self.domain += data[label: label + length].decode("utf-8") + "."
            # check if there is another label after this one
            head += length + 1
            length = data[head]

    def answer(self, ip_addr):
        # ** create the answer header **
        # copy the ID from incoming request
        packet = self.data[:2]
        # set response flags (assume RD=1 from request)
        packet += b"\x81\x80"
        # copy over QDCOUNT and set ANCOUNT equal
        packet += self.data[4:6] + self.data[4:6]
        # set NSCOUNT and ARCOUNT to 0
        packet += b"\x00\x00\x00\x00"

        # ** create the answer body **
        # respond with original domain name question
        packet += self.data[12:]
        # pointer back to domain name (at byte 12)
        packet += b"\xC0\x0C"
        # set TYPE and CLASS (A record and IN class)
        packet += b"\x00\x01\x00\x01"
        # set TTL to 60sec
        packet += b"\x00\x00\x00\x3C"
        # set response length to 4 bytes (to hold one IPv4 address)
        packet += b"\x00\x04"
        # now actually send the IP address as 4 bytes (without the "."s)
        packet += bytes(map(int, ip_addr.split(".")))

        gc.collect()

        return packet


class DNSServer:
    def __init__(self, ip_addr="192.168.4.1"):
        self._server_coro = None
        self._server_task: uasyncio.Task = None
        self.socket = None
        self.ip_addr = ip_addr

        self.loop = uasyncio.get_event_loop()

    async def _handler(self, data, sender):
        gc.collect()
        try:
            request = DNSQuery(data)
            logging.debug("Sending {:s} -> {:s}".format(request.domain, self.ip_addr))
            self.socket.sendto(request.answer(self.ip_addr), sender)
        except Exception as e:
            log.exc(e, "Error answering to UDP request")

    async def _udp_server(self, host, port):
        """UDP Server implementation.
        creates task for every new packet
        """
        addr = socket.getaddrinfo("0.0.0.0", port)[0][-1]
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setblocking(False)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(addr)

        log.info("DNS Server started, resolving all names to: {}".format(self.ip_addr))
        try:
            while True:
                yield uasyncio.core._io_queue.queue_read(self.socket)

                try:
                    data, sender = self.socket.recvfrom(1024)
                except Exception:
                    log.error("Error receiving UDP packet")
                    continue
                handler = self._handler(data, sender)
                self.loop.create_task(handler)
        except uasyncio.CancelledError:
            return
        finally:
            log.info("Closing UDP socket")
            self.socket.close()

    def run(self):
        self._server_coro = self._udp_server(self.ip_addr, 53)
        self._server_task = self.loop.create_task(self._server_coro)

    def shutdown(self):
        """Gracefully shutdown DNS Server"""
        log.info("Received DNS Server shutdown signal")
        self._server_task.cancel()
