import logging

from .imu import IMUServer
from .pressure import PressureServer
from .humidity import HumidityServer
from .stick import StickServer
from .screen import ScreenClient
from .lock import EmulatorLock

logger = logging.getLogger(__name__)

_ALREADY_RUNNING = 'Another process is currently acting as the Sense HAT emulator'


class EmulatorController:
    def __init__(self, simulate_imu=True, simulate_env=True):
        self.imu = self.pressure = self.humidity = None
        self.screen = self.stick = None
        self.lock = EmulatorLock('sense_emu_core')
        try:
            self.lock.acquire()
        except Exception as exc:
            raise RuntimeError(_ALREADY_RUNNING) from exc

        try:
            self.imu = IMUServer(simulate_world=simulate_imu)
            self.pressure = PressureServer(simulate_noise=simulate_env)
            self.humidity = HumidityServer(simulate_noise=simulate_env)
            self.screen = ScreenClient()
            self.stick = StickServer()
        except OSError as exc:
            # A server failed to bind its socket/port. This almost always means
            # another emulator instance is already running (holding the joystick
            # port), so surface it as the same friendly error and clean up.
            self.close()
            raise RuntimeError(_ALREADY_RUNNING) from exc
        except BaseException:
            # Anything else (corrupt shared file, struct.error, KeyboardInterrupt
            # ...) must not leave the lock held or servers half open.
            self.close()
            raise

    def close(self):
        # Close every subsystem even if one of them fails, and always release
        # the lock so the next launch can acquire it.
        try:
            for server in (self.imu, self.pressure, self.humidity,
                           self.screen, self.stick):
                if server is not None:
                    try:
                        server.close()
                    except Exception:
                        logger.exception('Error closing %s', type(server).__name__)
        finally:
            self.lock.release()
