from .imu import IMUServer
from .pressure import PressureServer
from .humidity import HumidityServer
from .stick import StickServer
from .screen import ScreenClient
from .lock import EmulatorLock

class EmulatorController:
    def __init__(self, simulate_imu=True, simulate_env=True):
        self.imu = self.pressure = self.humidity = None
        self.screen = self.stick = None
        self.lock = EmulatorLock('sense_emu_core')
        try:
            self.lock.acquire()
        except Exception:
            raise RuntimeError('Another process is currently acting as the Sense HAT emulator')

        try:
            self.imu = IMUServer(simulate_world=simulate_imu)
            self.pressure = PressureServer(simulate_noise=simulate_env)
            self.humidity = HumidityServer(simulate_noise=simulate_env)
            self.screen = ScreenClient()
            self.stick = StickServer()
        except OSError:
            # A server failed to bind its socket/port. This almost always means
            # another emulator instance is already running (holding the joystick
            # port), so surface it as the same friendly error and clean up.
            self.close()
            raise RuntimeError('Another process is currently acting as the Sense HAT emulator')

    def close(self):
        for server in (self.imu, self.pressure, self.humidity,
                       self.screen, self.stick):
            if server is not None:
                server.close()
        self.lock.release()
