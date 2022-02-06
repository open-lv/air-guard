import tinyweb
import os


class Portal:
    # Create web server application
    is_running = False
    server = tinyweb.webserver()

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
