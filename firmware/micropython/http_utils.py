import ussl
import usocket
import logging

log = logging.getLogger("http_utils")


def open_url(url, host=None, redirect_tries_left=1):
    proto, _, hostname, urlpath = url.split("/", 3)
    if not host:
        host = hostname
    try:
        port = 443
        if ":" in hostname:
            hostname, port = hostname.split(":")
            port = int(port)
        ai = usocket.getaddrinfo(host, port, 0, usocket.SOCK_STREAM)
    except OSError as e:
        raise Exception("Unable to resolve %s (no Internet?): OSError \"%s\"" % (hostname, e.errno))
    ai = ai[0]

    s = usocket.socket(ai[0], ai[1], ai[2])
    try:
        s.connect(ai[-1])

        if proto == "https:":
            s = ussl.wrap_socket(s, server_hostname=hostname)
            log.warning("Warning: %s SSL certificate is not validated" % hostname)

        # MicroPython rawsocket module supports file interface directly
        s.write("GET /%s HTTP/1.0\r\nHost: %s:%s\r\nUser-Agent: open-lv/air-guard\r\n\r\n" % (urlpath, hostname, port))
        l = s.readline()
        protover, status, msg = l.split(None, 2)
        if status.startswith(b"3"):
            if redirect_tries_left <= 0:
                raise Exception("Too many redirects")
            redirect_tries_left -= 1
            log.info("Redirect found")
            while True:
                l = s.readline()
                if not l:
                    raise ValueError("Unexpected EOF in finding Location")
                if l.startswith(b"Location:") or l.startswith(b"location:"):
                    s.close()
                    return open_url(l[10:].decode("ascii").rstrip(), None, redirect_tries_left)

        if status != b"200":
            if status == b"404":
                raise NotFoundError("404 not found")
            raise ValueError(status)
        while 1:
            l = s.readline()
            if not l:
                raise ValueError("Unexpected EOF in HTTP headers")
            if l == b"\r\n":
                break
    except Exception as e:
        s.close()
        raise e

    return s
