import logging
import uasyncio
import utime
import struct
import os


class CO2Plotter:
    """CO2Plotter is responsible not only for drawing the CO2 trend, but also for the data storage and processing"""
    data_buf = []
    last_add_ts = None
    last_save_ts = None
    avg_meas = None

    def __init__(self, time_scale_min, plot_w, plot_h, load_data=True):
        self.log = logging.getLogger("plot")
        self.time_scale_min = time_scale_min
        self.plot_w = plot_w
        self.plot_h = plot_h
        self.seconds_per_pix = time_scale_min * 60 / plot_w
        self.data_buf = [0] * self.plot_w
        self.data_insert_idx = 0
        if load_data:
            self._load_data()

    def add_measurement(self, m):
        """Add a new measurement to plotter state"""
        if self.avg_meas is None:
            self.avg_meas = float(m)
            self.last_add_ts = utime.ticks_ms()
            self.last_save_ts = utime.ticks_ms()
        else:
            self.avg_meas = float(self.avg_meas + m) / 2

        if (utime.ticks_ms() - self.last_add_ts) > self.seconds_per_pix * 1000:
            self.last_add_ts = utime.ticks_ms()

            if self.data_insert_idx == len(self.data_buf) - 1:
                # data buffer already full, shift the elements
                for i in range(1, len(self.data_buf)):
                    self.data_buf[i-1] = self.data_buf[i]

            self.data_buf[self.data_insert_idx] = int(self.avg_meas)
            if self.data_insert_idx < len(self.data_buf) - 1:
                self.data_insert_idx += 1

        if (utime.ticks_ms() - self.last_save_ts) > 10 * 60 * 1000:
            self._save_data()
            self.last_save_ts = utime.ticks_ms()

    def _load_data(self):
        """Load the binary-packed data from filesystem"""
        fn = "plot_%s.bin" % self.time_scale_min
        self.log.info("loading plot data from %s" % fn)
        try:
            with open(fn, "rb") as f:
                (self.data_insert_idx, ) = struct.unpack("h", f.read(2))
                data_tup = struct.unpack("%dh" % self.plot_w, f.read())
                self.data_buf = list(data_tup)
                self.log.info("%d points loaded" % self.data_insert_idx)
        except Exception as e:
            self.log.warning("failed to read data from file: %s" % e)
            try:
                os.remove(fn)
            except OSError:
                pass
            self.data_insert_idx = 0
            self.data_buf = [0] * self.plot_w

    def _save_data(self):
        """
        Save data to filesystem. In order to keep the writes to minimum, use binary representation and store
        each data point as 2 byte short
        """
        fn = "plot_%s.bin" % self.time_scale_min
        self.log.info("saving plot data to %s" % fn)
        with open(fn, "wb") as f:
            f.write(struct.pack("h", self.data_insert_idx))
            f.write(struct.pack("%dh" % self.plot_w, *self.data_buf))

    def have_enough_data(self) -> bool:
        return self.data_insert_idx > 5

    async def plot_data(self, screen, start_y=0):
        """
        Plot the data on screen starting at start_y offset
        """
        min_val = 16384
        max_val = 0
        for v in self.data_buf:
            if v == 0:
                break
            if v < min_val:
                min_val = v
            if v > max_val:
                max_val = v

        if min_val > max_val:
            return

        range_val = float(max_val - min_val)
        if range_val < 50:
            max_val = max_val + 25
            min_val = min_val - 25
            range_val = float(max_val - min_val)

        min_t = "%d ppm" % min_val
        screen.drawText(0, self.plot_h + 2, min_t)
        await uasyncio.sleep_ms(1)
        max_t = "%d ppm" % max_val
        screen.drawText(self.plot_w - screen.getTextWidth(max_t), 0, max_t)
        await uasyncio.sleep_ms(1)
        prev_y = None
        for i in range(len(self.data_buf)):
            v = self.data_buf[i]
            if v > 0:
                y = start_y + self.plot_h - int(((v - min_val) / range_val * self.plot_h))
                screen.drawPixel(i, y, 0xffffff)
                await uasyncio.sleep_ms(1)
                if prev_y is not None and abs(prev_y - y) > 1:
                    # fill in the y to connect the dots
                    for ny in range(min(prev_y, y), max(prev_y, y)):
                        screen.drawPixel(i, ny, 0xffffff)
                prev_y = y

