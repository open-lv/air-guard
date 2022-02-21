import logging
import network
import uasyncio
from uasyncio import CancelledError


class NetworkManager:
    MAX_CONNECTION_ATTEMPTS = 10

    def __init__(self, wifi_ssid, wifi_password, captive_portal_enabled=False, captive_portal_ssid=None,
                 on_connecting=None,
                 on_disconnected=None, on_connected=None, on_ap_enabled=None):
        self._log = logging.getLogger("network_manager")

        self.wifi_ssid = wifi_ssid
        self.wifi_password = wifi_password

        self._captive_portal_enabled = captive_portal_enabled
        self._captive_portal_ssid = captive_portal_ssid

        self._on_connecting = on_connecting
        self._on_disconnected = on_disconnected
        self._on_connected = on_connected
        self._on_ap_enabled = on_ap_enabled

        self._sta_if = network.WLAN(network.STA_IF)
        self._ap_if = network.WLAN(network.AP_IF)

        self._network_manager_coro = None
        self._network_manager_task: uasyncio.Task = None

    async def _network_manager(self):
        wifi_ssid = self.wifi_ssid
        wifi_password = self.wifi_password
        captive_portal_enabled = self._captive_portal_enabled

        connected_once = False
        self._is_wifi_connected = False

        while True:
            try:
                if self._sta_if.isconnected():
                    self._log.debug("WIFI still connected")
                    await uasyncio.sleep(30)
                    continue

                self._log.info("WIFI disconnected")
                self._is_wifi_connected = False
                if connected_once and self._on_disconnected:
                    self._on_disconnected()

                self._reset_network_services()

                if not await self._connect_to_wifi(wifi_ssid, wifi_password):
                    if not connected_once and captive_portal_enabled:
                        self._enable_ap()
                        return
                    else:
                        self._log.info("Could not establish WIFI connection, retrying in 30 seconds...")
                        await uasyncio.sleep(30)
                        continue

                self._log.info("WiFi connected, ifconfig: %s" % str(self._sta_if.ifconfig()))

                self._is_wifi_connected = True
                if self._on_connected:
                    self._on_connected()
                connected_once = True

                await uasyncio.sleep(30)
            except Exception as e:
                self._log.warning("Exception during wifi connection: %s" % e)
                self._reset_network_services()
                await uasyncio.sleep(30)
            except CancelledError:
                self._log.info("Network manager stop signal received. Stopping...")
                self._reset_network_services()
                raise

    async def _connect_to_wifi(self, wifi_ssid, wifi_password):
        self._log.info("Trying to connect to SSID {}".format(wifi_ssid))
        self._sta_if.active(False)
        self._sta_if.active(True)
        self._sta_if.connect(wifi_ssid, wifi_password)

        if self._on_connecting:
            self._on_connecting()

        station_connect_attempts = 0
        while station_connect_attempts <= self.MAX_CONNECTION_ATTEMPTS:
            if not self._sta_if.isconnected():
                self._log.info(
                    "Connection attempt {:d}/{:d} ...".format(station_connect_attempts, self.MAX_CONNECTION_ATTEMPTS))
                await uasyncio.sleep(3)
                station_connect_attempts += 1
            else:
                self._log.info("WIFI connected to {:s}".format(wifi_ssid))
                return True

        self._sta_if.active(False)

        return False

    def _reset_network_services(self):
        self._log.info("Resetting network services")

        self._sta_if.active(False)
        self._ap_if.active(False)

    def _enable_ap(self):
        self._log.info("Enabling captive AP until network manager restarted or device rebooted")
        self._ap_if.active(True)
        self._ap_if.config(essid=self._captive_portal_ssid, authmode=network.AUTH_OPEN)
        ifconfig = self._ap_if.ifconfig()
        self._log.info("WiFi AP %s Enabled, ifconfig: %s" % (self._captive_portal_ssid, str(ifconfig)))

        import captive_dns_server
        self._captive_dns_server = captive_dns_server.DNSServer(ifconfig[0])
        self._captive_dns_server.run()

        if self._on_ap_enabled:
            self._on_ap_enabled()

    def restart(self):
        self.stop()
        self.start()

    def stop(self):
        if self._network_manager_task:
            self._network_manager_task.cancel()

        self._network_manager_coro = None
        self._network_manager_task = None

    def start(self):
        if self._network_manager_coro:
            self._log.warning("NetworkManager already running")
            return

        self._network_manager_coro = self._network_manager()
        self._network_manager_task = uasyncio.create_task(self._network_manager_coro)
