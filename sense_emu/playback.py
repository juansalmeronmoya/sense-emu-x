import threading
from time import time

from .recfile import parse_recording


class Player:
    """Inject a recorded .bin file into live emulator servers."""

    def __init__(self, imu, pressure, humidity):
        self._imu = imu
        self._pressure = pressure
        self._humidity = humidity
        self._stop_event = threading.Event()
        self._thread = None

        self.running = False
        self.progress = 0.0
        self.position = 0
        self.total = 0
        self.current = None

    def play(self, path):
        """Parse *path* and start injecting in a daemon thread."""
        if self.running:
            return
        records = parse_recording(path)
        if not records:
            return
        self._stop_event.clear()
        self.progress = 0.0
        self.position = 0
        self.total = len(records)
        self.current = None
        self.running = True
        self._thread = threading.Thread(
            target=self._worker, args=(records,), daemon=True)
        self._thread.start()

    def stop(self):
        """Signal the worker to stop and wait for it to finish."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self.running = False

    def _worker(self, records):
        imu = self._imu
        psensor = self._pressure
        hsensor = self._humidity

        saved_world = imu.simulate_world
        saved_pnoise = psensor.simulate_noise
        saved_hnoise = hsensor.simulate_noise

        imu.simulate_world = False
        psensor.simulate_noise = False
        hsensor.simulate_noise = False

        try:
            t0_rec = records[0].timestamp
            t0_wall = time()
            total = len(records)

            for i, rec in enumerate(records):
                if self._stop_event.is_set():
                    break

                delta = (rec.timestamp - t0_rec) - (time() - t0_wall)
                if delta > 0:
                    self._stop_event.wait(timeout=delta)
                if self._stop_event.is_set():
                    break

                psensor.set_values(rec.pressure, rec.ptemp)
                hsensor.set_values(rec.humidity, rec.htemp)
                imu.set_imu_values(
                    (rec.ax, rec.ay, rec.az),
                    (rec.gx, rec.gy, rec.gz),
                    (rec.cx, rec.cy, rec.cz),
                    (rec.ox, rec.oy, rec.oz),
                )

                self.current = rec
                self.position = i + 1
                self.progress = (i + 1) / total
        finally:
            imu.simulate_world = saved_world
            psensor.simulate_noise = saved_pnoise
            hsensor.simulate_noise = saved_hnoise
            self.running = False
