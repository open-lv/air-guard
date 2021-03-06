import gc
import network

import sys

import os
import uerrno
import ujson
import usocket
import ussl
import utarfile
import utime
import machine
import ota_utils
import http_utils
import display

class NotFoundError(Exception):
    pass


class OTA:
    def __init__(self):
        self.file_buf = bytearray(512)
        self.debug = True
        self.warn_ussl = True
        self.gzdict_sz = 16 + 15
        self.ota_started_time = None

    def is_ota_in_progress(self):
        try:
            with open("_ota_status", "r") as f:
                return f.read() == ota_utils.STATUS_IN_PROGRESS
        except:
            pass
        return False

    def reset_ota_state(self, status):
        try:
            with open("_ota_status", "w") as f:
                f.write(status)
        except Exception as e:
            self._log("!!! Failed to reset OTA state !!!")
            self._log_exception(e)
            sys.exit(1)

    def connect_to_network(self):
        import config
        sta_if = network.WLAN(network.STA_IF)
        sta_if.active(True)
        wifi_ssid = config.sargsConfig.WIFI_SSID
        wifi_password = config.sargsConfig.WIFI_PASSWORD
        sta_if.connect(wifi_ssid, wifi_password)

        attempts = 10
        station_connect_attempts = 0
        while station_connect_attempts <= attempts:
            if not sta_if.isconnected():
                self._log("Connection attempt {:d}/{:d} ...".format(station_connect_attempts, attempts))
                utime.sleep(1)
                station_connect_attempts += 1
            else:
                self._log("WIFI connected to {:s}".format(wifi_ssid))
                return True

        sta_if.active(False)
        return False

    def draw_hcenter_text(self, y, text):
        x = (display.width() - display.getTextWidth(text)) // 2
        display.drawText(x, y, text)

    def display_update_info(self, name):
        display.drawFill(0)
        self.draw_hcenter_text(10, "Ielade")
        self.draw_hcenter_text(25, "atjauninajumu...")
        self.draw_hcenter_text(45, "versija: " + name)
        display.flush()

    def perform_update(self, name):
        self.clear_log_file()
        self.display_update_info(name)
        try:
            self.ota_started_time = utime.ticks_ms()
            if self.is_ota_in_progress():
                self._log("OTA already in progress, resetting state")
                ota_utils.restore_original()
                return self.reset_ota_state(ota_utils.STATUS_CANCELLED)

            self._log('Starting OTA update: "%s"' % name)
            with open("_ota_status", "w") as f:
                f.write(ota_utils.STATUS_IN_PROGRESS)

            self.connect_to_network()

            self._log("Synchronizing time from NTP")
            import ntptime
            ntptime.settime()
            self._log("Current time: %d-%d-%d %d:%d:%d.%d.%d" % utime.gmtime())

            gc.collect()

            release = self.select_release(name)

            dir_name = release["name"].replace(".", "_").replace("-", "_")

            ota_utils.remove_all_versions()

            self.download_and_install(dir_name, release["asset_url"])

            with open("main.py", "w") as f:
                f.write("import %s.main\n" % dir_name)
                f.write("%s.main.run()\n" % dir_name)

            self.reset_ota_state(ota_utils.STATUS_FINISHED)
            self._log('OTA update completed successfully in %d seconds: "%s" "%s"' % (
                (utime.ticks_ms() - self.ota_started_time) / 1000, name, release["asset_url"]))
        except Exception as e:
            self._log('Error performing OTA update: "%s"' % name)
            self._log_exception(e)
            ota_utils.restore_original()
            self.reset_ota_state(ota_utils.STATUS_FAILED)
        finally:
            print("Resetting device")
            machine.reset()

    def get_releases(self):
        releases = ujson.load(http_utils.open_url("https://api.github.com/repos/open-lv/air-guard/releases"))
        micropython_releases = []
        for release in releases:
            if not release["tag_name"].startswith("micropython-"):
                continue
            for asset in release["assets"]:
                if not asset["name"] == "micropython.tar":
                    continue
                micropython_releases.append({"name": release["tag_name"], "asset_url": asset["browser_download_url"]})
                break

        return micropython_releases

    def select_release(self, name):
        full_version_name = "micropython-" + name
        for release in self.get_releases():
            if release["name"] == full_version_name:
                return release
        raise Exception('Error retrieving release "%s"' % name)

    def download_and_install(self, name, tar_url):
        f1 = http_utils.open_url(tar_url)
        try:
            f2 = utarfile.TarFile(fileobj=f1)
            self.install_tar(f2, name + "/")
        finally:
            f1.close()
        del f2
        gc.collect()

    def save_file(self, fname, subf):
        with open(fname, "wb") as outf:
            while True:
                sz = subf.readinto(self.file_buf)
                if not sz:
                    break
                outf.write(self.file_buf, sz)

    # Expects *file* name
    def _makedirs(self, name):
        ret = False
        s = ""
        comps = name.rstrip("/").split("/")[:-1]
        if comps[0] == "":
            s = "/"
        for c in comps:
            if s and s[-1] != "/":
                s += "/"
            s += c
            try:
                os.mkdir(s)
                ret = True
            except OSError as e:
                if e.errno != uerrno.EEXIST and e.errno != uerrno.EISDIR:
                    raise e
                ret = False
        return ret

    def install_tar(self, f, prefix):
        for info in f:
            fname = info.name
            outfname = prefix + fname
            if info.type != utarfile.DIRTYPE:
                if self.debug:
                    self._log("Extracting " + outfname)
                self._makedirs(outfname)
                subf = f.extractfile(info)
                self.save_file(outfname, subf)

    def fatal(self, msg, exc=None):
        self._log("Error:", msg)
        if exc and self.debug:
            raise exc
        sys.exit(1)

    def _log(self, message):
        message = '{0: > 6}: {1}'.format((utime.ticks_ms() - self.ota_started_time), message)
        print(message)
        with open("_ota_logs", "a") as f:
            print(message, file=f)

    def _log_exception(self, exception):
        sys.print_exception(exception)
        with open("_ota_logs", "a") as f:
            sys.print_exception(exception, f)

    def clear_log_file(self):
        with open("_ota_logs", "w") as f:
            pass

