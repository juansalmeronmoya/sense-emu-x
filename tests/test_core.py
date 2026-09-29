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


class TestEmulatorControllerCleanup:
    """Any failure while building the controller - not just OSError - must
    close what was already opened and release the lock (P0-4)."""

    def test_unexpected_error_is_reraised_unchanged(self, emulator_patches):
        with patch('sense_emu.core.HumidityServer',
                   side_effect=ValueError('corrupt shared file')):
            with pytest.raises(ValueError, match='corrupt shared file'):
                EmulatorController(simulate_imu=False, simulate_env=False)

    def test_unexpected_error_releases_lock(self, emulator_patches):
        from sense_emu.lock import EmulatorLock
        with patch('sense_emu.core.HumidityServer', side_effect=ValueError):
            with pytest.raises(ValueError):
                EmulatorController(simulate_imu=False, simulate_env=False)
        assert EmulatorLock('check')._is_held() is False

    def test_servers_opened_before_failure_are_closed(self, emulator_patches):
        import struct
        opened = []
        from sense_emu import core
        real_imu, real_pressure = core.IMUServer, core.PressureServer

        def spy(real):
            def factory(*args, **kwargs):
                server = real(*args, **kwargs)
                opened.append(server)
                return server
            return factory

        with patch('sense_emu.core.IMUServer', side_effect=spy(real_imu)), \
             patch('sense_emu.core.PressureServer', side_effect=spy(real_pressure)), \
             patch('sense_emu.core.HumidityServer', side_effect=struct.error):
            with pytest.raises(struct.error):
                EmulatorController(simulate_imu=False, simulate_env=False)
        assert len(opened) == 2
        assert all(server._fd is None for server in opened)

    def test_keyboard_interrupt_still_cleans_up(self, emulator_patches):
        from sense_emu.lock import EmulatorLock
        with patch('sense_emu.core.ScreenClient', side_effect=KeyboardInterrupt):
            with pytest.raises(KeyboardInterrupt):
                EmulatorController(simulate_imu=False, simulate_env=False)
        assert EmulatorLock('check')._is_held() is False

    def test_lock_failure_is_reported_as_runtimeerror(self, emulator_patches):
        with patch('sense_emu.core.EmulatorLock') as lock_cls:
            lock_cls.return_value.acquire.side_effect = FileExistsError
            with pytest.raises(RuntimeError, match='Another process'):
                EmulatorController(simulate_imu=False, simulate_env=False)

    def test_close_continues_after_a_failing_subsystem(self, emulator):
        real_close = emulator.imu.close
        emulator.imu.close = MagicMock(side_effect=RuntimeError('boom'))
        emulator.close()   # must not raise
        assert emulator.pressure._fd is None
        assert emulator.humidity._fd is None
        assert emulator.lock.mine is False
        real_close()       # release the real IMU file we bypassed

    def test_close_is_idempotent(self, emulator):
        emulator.close()
        emulator.close()
