from .imu import IMUServer
from .pressure import PressureServer
from .humidity import HumidityServer
from .stick import StickServer
from .screen import ScreenClient
from .lock import EmulatorLock

class EmulatorController:
    def __init__(self, simulate_imu=True, simulate_env=True):
        self.lock = EmulatorLock('sense_emu_core')
        try:
            self.lock.acquire()
        except:
            raise RuntimeError('Another process is currently acting as the Sense HAT emulator')
            
        self.imu = IMUServer(simulate_world=simulate_imu)
        self.pressure = PressureServer(simulate_noise=simulate_env)
        self.humidity = HumidityServer(simulate_noise=simulate_env)
        self.screen = ScreenClient()
        self.stick = StickServer()

    def close(self):
        self.imu.close()
        self.pressure.close()
        self.humidity.close()
        self.screen.close()
        self.stick.close()
        self.lock.release()
