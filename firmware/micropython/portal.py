import ujson as json

import tinyweb
import os
import binascii

from sargs import sargs
import sargsui


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


class CaptiveWebserver(tinyweb.webserver):
    def __init__(self, ip_addr, request_timeout=3, max_concurrency=3, backlog=16, debug=False):
        super().__init__(request_timeout, max_concurrency, backlog, debug)
        self.redirect_url = 'http://{}/'.format(ip_addr)
        self.ip_addr = ip_addr.encode()

    async def _redirect_handler(req, resp: tinyweb.response, redirect_uri):
        await resp.redirect(redirect_uri)

    async def _handle_request(self, req, resp):
        if sargs.ui.wifi_state != sargsui.WiFiState.ACCESS_POINT:
            await super()._handle_request(req, resp)
            return

        await req.read_request_line()
        # Find URL handler
        req.handler, req.params = self._find_url_handler(req)
        if not req.handler:
            req.params = {'methods': [b'GET'],
                          'save_headers': [b'Host'],
                          'max_body_size': 1024,
                          'allowed_access_control_headers': '*',
                          'allowed_access_control_origins': '*',
                          }

            # No URL handler found - read response and issue HTTP 404
            await req.read_headers(req.params['save_headers'])

            if b'Host' not in req.headers or req.headers[b'Host'] != self.ip_addr:
                req._param = self.redirect_url
                req.handler = CaptiveWebserver._redirect_handler
                return

            raise tinyweb.HTTPException(404)

        req.params['save_headers'].append(b'Host')
        resp.params = req.params
        # Read / parse headers
        await req.read_headers(req.params['save_headers'])

        if b'Host' not in req.headers or req.headers[b'Host'] != self.ip_addr:
            req._param = self.redirect_url
            req.handler = CaptiveWebserver._redirect_handler


class Portal:
    # Create web server application
    is_running = False
    server = CaptiveWebserver('192.168.4.1')

    @server.route('/')
    async def index(request, response):
        await response.send_file('static/index.html.gz', content_type="text/html; charset=UTF-8",
                                 content_encoding="gzip")

    @server.resource('/api/state')
    def sargsState(self):
        is_connected = sargs.ui.wifi_state == sargsui.WiFiState.CONNECTED
        is_internet = sargs.ui.internet_state == sargsui.InternetState.CONNECTED
        connected_ssid = sargs.get_connected_ssid()

        return {
            "co2": {
                "ppm": sargs.co2_measurement,
                "status": "AIR_QUALITY_UNKNOWN"
            },
            "wifi": {
                "connected": is_connected,
                "internet": is_internet,
                "ssid": connected_ssid,
            }
        }

    @server.resource('/api/stations')
    async def stations(self):
        access_points = sargs.get_wifi_ap_list()

        yield "["
        last_station = access_points[-1]
        for station in access_points:
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


def setup():
    portal = Portal()
    add_static_routes(portal)
    portal.setup()
