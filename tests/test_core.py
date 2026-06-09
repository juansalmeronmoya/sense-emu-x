import pytest
from unittest.mock import patch, MagicMock, call
from sense_emu.core import EmulatorController


class TestEmulatorController:
    def test_creates_all_subsystems(self, emulator):
        assert emulator.imu is not None
        assert emulator.pressure is not None
        assert emulator.humidity is not None
        assert emulator.screen is not None
        assert emulator.stick is not None

    def test_lock_is_held_after_init(self, emulator):
        assert emulator.lock.mine is True

    def test_close_releases_lock(self, emulator):
        emulator.close()
        assert emulator.lock.mine is False
        # Re-close should not raise (idempotent subsystems)

    def test_close_imu(self, emulator):
        # After close, the mmap should be None
        emulator.close()
        assert emulator.imu._fd is None

    def test_close_pressure(self, emulator):
        emulator.close()
        assert emulator.pressure._fd is None

    def test_close_humidity(self, emulator):
        emulator.close()
        assert emulator.humidity._fd is None

    def test_close_screen(self, emulator):
        emulator.close()
        assert emulator.screen._fd is None

    def test_sensor_values_readable(self, emulator):
        # Default values without noise
        assert emulator.pressure.pressure == pytest.approx(1013.0)
        assert emulator.humidity.humidity == pytest.approx(45.0)

    def test_set_imu_orientation(self, emulator):
        import numpy as np
        emulator.imu.set_orientation((10.0, 20.0, 30.0))
        np.testing.assert_array_almost_equal(
            emulator.imu.orientation, [10.0, 20.0, 30.0]
        )

    def test_set_pressure_values(self, emulator):
        emulator.pressure.set_values(950.0, 18.0)
        assert emulator.pressure.pressure == pytest.approx(950.0)
        assert emulator.pressure.temperature == pytest.approx(18.0)

    def test_set_humidity_values(self, emulator):
        emulator.humidity.set_values(60.0, 22.0)
        assert emulator.humidity.humidity == pytest.approx(60.0)

    def test_duplicate_controller_raises(self, emulator):
        # emulator holds the lock; a second EmulatorController must fail
        with pytest.raises((RuntimeError, FileExistsError)):
            EmulatorController(simulate_imu=False, simulate_env=False)


class TestEmulatorControllerBindFailure:
    """A server failing to bind (e.g. another instance holds the joystick port)
    must surface as a clean RuntimeError and must release the lock."""

    def test_bind_failure_raises_runtimeerror(self, emulator_patches):
        import errno
        with patch('sense_emu.core.StickServer',
                   side_effect=OSError(errno.EADDRINUSE, 'address in use')):
            with pytest.raises(RuntimeError):
                EmulatorController(simulate_imu=False, simulate_env=False)

    def test_bind_failure_releases_lock(self, emulator_patches):
        import errno
        from sense_emu.lock import EmulatorLock
        with patch('sense_emu.core.StickServer',
                   side_effect=OSError(errno.EADDRINUSE, 'address in use')):
            with pytest.raises(RuntimeError):
                EmulatorController(simulate_imu=False, simulate_env=False)
        # Lock must be free afterwards so the next launch can acquire it
        assert EmulatorLock('check')._is_held() is False
