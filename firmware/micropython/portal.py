import tinyweb


class Portal:
    # Create web server application
    is_running = False
    portal = tinyweb.webserver()

    # Index page
    @portal.route('/')
    async def index(request, response):
        await response.send_file('static/index.html', content_type='text/html; charset=UTF-8')

    def setup(self):
        self.portal.run(host="0.0.0.0", port=80, loop_forever=False)
        self.is_running = True


def setup():
    portal = Portal()
    portal.setup()
