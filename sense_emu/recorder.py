import threading
from time import time, sleep

from .common import HEADER_REC, DATA_REC
from . import RTIMU as _rtimu_mod


class Recorder:
    """Record live emulator readings to a .bin file."""

    DEFAULT_INTERVAL = 0.1  # seconds (10 Hz)

    def __init__(self, path, interval=DEFAULT_INTERVAL):
        self._path = path
        self._interval = interval
        self._stop_event = threading.Event()
        self._thread = None
        self.running = False
        self.record_count = 0

    def start(self):
        if self.running:
            return
        self._stop_event.clear()
        self.record_count = 0
        self.running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self.running = False

    def _worker(self):
        settings = _rtimu_mod.Settings('')
        imu = _rtimu_mod.RTIMU(settings)
        imu.IMUInit()
        psensor = _rtimu_mod.RTPressure(settings)
        psensor.pressureInit()
        hsensor = _rtimu_mod.RTHumidity(settings)
        hsensor.humidityInit()
        interval = self._interval
        nan = float('nan')

        try:
            with open(self._path, 'wb') as f:
                f.write(HEADER_REC.pack(b'SENSEHAT', 1, time()))
                while not self._stop_event.is_set():
                    timestamp = time()
                    if imu.IMURead():
                        ax, ay, az = imu.getAccel()
                        gx, gy, gz = imu.getGyro()
                        cx, cy, cz = imu.getCompass()
                        ox, oy, oz = imu.getFusionData()
                        pvalid, pressure, ptvalid, ptemp = psensor.pressureRead()
                        hvalid, humidity, htvalid, htemp = hsensor.humidityRead()
                        f.write(DATA_REC.pack(
                            timestamp,
                            pressure if pvalid else nan,
                            ptemp if ptvalid else nan,
                            humidity if hvalid else nan,
                            htemp if htvalid else nan,
                            ax, ay, az,
                            gx, gy, gz,
                            cx, cy, cz,
                            ox, oy, oz,
                        ))
                        self.record_count += 1
                    delay = max(0.0, timestamp + interval - time())
                    if delay:
                        self._stop_event.wait(timeout=delay)
        finally:
            self.running = False
