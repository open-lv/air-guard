import ujson as json

import tinyweb
import os
import binascii

from sargs import sargs


def decode_station_authmode(authmode):
    if authmode == 0:
        return "open"
    if authmode == 1:
        return "wep"
    if authmode == 2:
        return "wpa-psk"
    if authmode == 3:
        return "wpa2-psk"
    if authmode == 4:
        return "wpa/wpa2-psk"
    return "unknown"


class Portal:
    # Create web server application
    is_running = False
    server = tinyweb.webserver()

    @server.resource('/api/state')
    def sargsState(self):
        return {
            "co2": {
                "ppm": sargs.co2_measurement,
                "status": "AIR_QUALITY_UNKNOWN"
            },
            "wifi": {
                "connected": sargs.sta_if.isconnected(),
                "internet": False
            }
        }

    @server.resource('/api/stations')
    async def stations(self):
        stations = sargs.sta_if.scan()

        yield "["
        last_station = stations[-1]
        for station in stations:
            yield json.dumps({
                "ssid": station[0],
                "bssid": binascii.hexlify(station[1], b':'),
                "channel": station[2],
                "rssi": station[3],
                "authmode": decode_station_authmode(station[4]),
                "hidden": station[5]
            })
            if station != last_station:
                yield ","

        yield "]"

    async def serveStaticFile(request, response):
        path = request.path.decode()
        content_type = 'plain/text'
        if path.endswith('.html'):
            content_type = 'text/html'
        if path.endswith('.js'):
            content_type = 'text/javascript'
        if path.endswith('.css'):
            content_type = 'text/css'
        if path.endswith('.svg'):
            content_type = 'image/svg+xml'
        await response.send_file("static" + path + ".gz", content_type=content_type + "; charset=UTF-8",
                                 content_encoding="gzip")

    def setup(self):
        self.server.run(host="0.0.0.0", port=80, loop_forever=False)
        self.is_running = True


def add_static_routes(portal, dir="static"):
    for record in os.listdir(dir):
        try:
            os.listdir(dir + "/" + record)
            add_static_routes(portal, dir + "/" + record)
            continue
        except:
            pass

        if dir == "static":
            base_path = ""
        else:
            base_path = "/" + dir[7:]

        # GZipped, remove .gz
        path = "{0}/{1}".format(base_path, record)[:-3]
        print("Adding static route: {0}".format(path))
        portal.server.add_route(path, Portal.serveStaticFile)

        if path == '/index.html':
            print("Adding default `/` route to index.html")
            portal.server.add_route('/', Portal.serveStaticFile)


def setup():
    portal = Portal()
    add_static_routes(portal)
    portal.setup()
