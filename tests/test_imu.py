import time
import math
import pytest
import numpy as np
from sense_emu.imu import (
    IMUServer, IMU_DATA, ACCEL_FACTOR, GYRO_FACTOR,
    COMPASS_FACTOR, ORIENT_FACTOR, timestamp, imu_filename,
)


@pytest.fixture
def server(tmp_imu_file):
    srv = IMUServer(simulate_world=False)
    yield srv
    srv.close()


@pytest.fixture
def server_world(tmp_imu_file):
    srv = IMUServer(simulate_world=True)
    yield srv
    srv.close()


class TestTimestamp:
    def test_returns_int(self):
        ts = timestamp()
        assert isinstance(ts, int)

    def test_increasing(self):
        t1 = timestamp()
        time.sleep(0.01)
        t2 = timestamp()
        assert t2 > t1

    def test_microsecond_resolution(self):
        ts = timestamp()
        assert ts > 1_000_000  # at least 1 second of uptime in µs


class TestImuFilename:
    def test_returns_string(self):
        assert isinstance(imu_filename(), str)
        assert 'imu' in imu_filename()


class TestIMUServerBasic:
    def test_sensor_type_initialized(self, server):
        data = server._read()
        assert data.type == 6

    def test_sensor_name_initialized(self, server):
        data = server._read()
        assert b'LSM9DS1' in data.name

    def test_initial_orientation_zero(self, server):
        np.testing.assert_array_equal(server.orientation, [0, 0, 0])

    def test_initial_accel_zero(self, server):
        np.testing.assert_array_equal(server.accel, [0, 0, 0])

    def test_set_orientation_stores_value(self, server):
        server.set_orientation((10.0, 20.0, 30.0))
        np.testing.assert_array_almost_equal(server.orientation, [10.0, 20.0, 30.0])

    def test_set_orientation_with_position(self, server):
        server.set_orientation((0.0, 0.0, 0.0), position=(1.0, 0.0, 0.0))
        np.testing.assert_array_almost_equal(server.position, [1.0, 0.0, 0.0])

    def test_set_imu_values_direct(self, server):
        server.set_imu_values(
            accel=(0.1, 0.2, 9.8),
            gyro=(0.0, 0.0, 0.1),
            compass=(0.3, 0.0, 0.0),
            orientation=(5.0, 10.0, 15.0),
        )
        data = server._read()
        assert data.accel[2] > 0  # Z accel should be positive

    def test_set_imu_values_written_to_mmap(self, server):
        server.set_imu_values(
            accel=(0.0, 0.0, 1.0),
            gyro=(0.0, 0.0, 0.0),
            compass=(0.33, 0.0, 0.0),
            orientation=(0.0, 0.0, 0.0),
        )
        data = server._read()
        expected_az = int(1.0 * ACCEL_FACTOR)
        assert abs(data.accel[2] - expected_az) <= 1

    def test_close_is_idempotent(self, tmp_imu_file):
        srv = IMUServer(simulate_world=False)
        srv.close()
        srv.close()

    def test_simulate_world_false_by_fixture(self, server):
        assert server.simulate_world is False


class TestIMUSimulateWorld:
    def test_simulate_world_starts_thread(self, server_world):
        assert server_world.simulate_world is True

    def test_enable_then_disable_world(self, server):
        server.simulate_world = True
        assert server.simulate_world is True
        time.sleep(0.05)
        server.simulate_world = False
        assert server.simulate_world is False

    def test_world_updates_timestamp(self, server_world):
        t1 = server_world._read().timestamp
        time.sleep(0.05)
        t2 = server_world._read().timestamp
        assert t2 >= t1


class TestIMUPerturb:
    def test_perturb_vector_close(self, server):
        v = np.array([1.0, 2.0, 3.0])
        for _ in range(50):
            result = server._perturb(v, 1.0)
            for i in range(3):
                assert abs(result[i] - v[i]) < 2.0


class TestWorldState:
    def test_accel_matches_gravity_when_flat(self, server):
        server.set_orientation((0.0, 0.0, 0.0))
        # Advance the generator past its time threshold by waiting
        import time as _time
        _time.sleep(0.02)
        server._world_write()
        data = server._read()
        # When flat, Z accel should be positive (gravity direction)
        assert data.accel[2] >= 0

    def test_orientation_written_in_radians_scaled(self, server):
        server.set_orientation((45.0, 0.0, 0.0))
        server._world_write()
        data = server._read()
        expected = int(math.radians(45.0) * ORIENT_FACTOR)
        assert abs(data.orient[0] - expected) <= 2


import numpy as np
from unittest.mock import patch
import os
from sense_emu.imu import (
    imu_filename, init_imu, IMUServer, IMU_DATA, IMUData,
    ACCEL_FACTOR, GYRO_FACTOR, COMPASS_FACTOR, timestamp,
    V, O,
)


class TestImuFilenameExtended:
    def test_no_shm_uses_tmp(self):
        with patch('sys.platform', 'linux'), \
             patch('os.path.exists', return_value=False):
            result = imu_filename()
        import os
        assert result == os.path.join('/tmp', 'rpi-sense-emu-imu')

    def test_windows_path(self):
        with patch('sys.platform', 'win32'), \
             patch.dict('os.environ', {'TEMP': '/tmp/wintemp'}):
            result = imu_filename()
        assert 'rpi-sense-emu-imu' in result


class TestInitImu:
    def test_creates_file_when_missing(self, tmp_path):
        path = str(tmp_path / 'new_imu')
        with patch('sense_emu.imu.imu_filename', return_value=path):
            fd = init_imu()
        assert os.path.exists(path)
        fd.close()

    def test_truncates_oversized_file(self, tmp_path):
        path = str(tmp_path / 'oversized_imu')
        with open(path, 'wb') as f:
            f.write(b'\x00' * (IMU_DATA.size + 50))
        with patch('sense_emu.imu.imu_filename', return_value=path):
            fd = init_imu()
        fd.close()
        assert os.path.getsize(path) == IMU_DATA.size

    def test_skips_truncate_when_correct_size(self, tmp_path):
        path = str(tmp_path / 'correct_imu')
        with open(path, 'wb') as f:
            f.write(b'\xAB' * IMU_DATA.size)
        with patch('sense_emu.imu.imu_filename', return_value=path):
            fd = init_imu()
        fd.close()
        assert os.path.getsize(path) == IMU_DATA.size


class TestIMUServerExtended:
    def test_already_initialized_branch(self, tmp_path):
        path = str(tmp_path / 'imu')
        accel = V(0.0, 0.0, 1.0) * ACCEL_FACTOR
        gyro_val = V(0.01, 0.0, 0.0) * GYRO_FACTOR
        compass = V(0.33, 0.0, 0.0) * COMPASS_FACTOR
        with open(path, 'wb') as f:
            f.write(IMU_DATA.pack(
                6, b'LSM9DS1', timestamp(),
                int(accel[0]), int(accel[1]), int(accel[2]),
                int(gyro_val[0]), int(gyro_val[1]), int(gyro_val[2]),
                int(compass[0]), int(compass[1]), int(compass[2]),
                0, 0, 0,
            ))
        with patch('sense_emu.imu.imu_filename', return_value=path):
            server = IMUServer(simulate_world=False)
        server.close()

    def test_gyro_property(self, server):
        val = server.gyro
        assert val is not None

    def test_compass_property(self, server):
        val = server.compass
        assert val is not None

    def test_set_orientation_simulate_world_true(self, tmp_imu_file):
        server = IMUServer(simulate_world=True)
        server.set_orientation((10.0, 20.0, 30.0))
        np.testing.assert_array_almost_equal(server.orientation, [10.0, 20.0, 30.0])
        server.close()


# ---------------------------------------------------------------------------
# P0-1: the gyroscope is reported in rad/s (as on the real hardware), not deg/s
# ---------------------------------------------------------------------------

from unittest.mock import patch as _patch                      # noqa: E402

from sense_emu.imu import GYRO_MAX, GYRO_NOISE, V as _V        # noqa: E402


def _gyro_after(server, start, end, seconds):
    """
    Drive the simulation's state generator by hand: orientation *start* at
    t=0, then *end* after *seconds*. Returns the gyro reading it yields.
    """
    micro = int(seconds * 1_000_000)
    server._orientation = _V(*start)
    with _patch('sense_emu.imu.timestamp',
                side_effect=[1_000_000, 1_000_000, 1_000_000 + micro]):
        states = server._world_state()
        next(states)                       # primes 'then' / initial orientation
        server._orientation = _V(*end)
        _, _, gyro, _ = next(states)
    return gyro


class TestGyroUnits:
    def test_turn_rate_is_radians_per_second(self, server):
        # 90 degrees about z in one second is pi/2 rad/s (the old code
        # reported 90, i.e. 57x too large)
        gyro = _gyro_after(server, (0, 0, 0), (0, 0, 90), 1.0)
        assert gyro[2] == pytest.approx(math.pi / 2)
        assert gyro[0] == pytest.approx(0.0)
        assert gyro[1] == pytest.approx(0.0)

    def test_rate_scales_with_elapsed_time(self, server):
        gyro = _gyro_after(server, (0, 0, 0), (36, 0, 0), 0.5)
        assert gyro[0] == pytest.approx(math.radians(72))

    def test_negative_rotation(self, server):
        gyro = _gyro_after(server, (0, 0, 0), (0, -45, 0), 1.0)
        assert gyro[1] == pytest.approx(-math.radians(45))

    @pytest.mark.parametrize('start,end', [(179, -179), (-179, 179)])
    def test_angle_wraparound_is_a_short_turn(self, server, start, end):
        # Crossing +/-180 is a 2 degree turn, not a 358 degree one; the old
        # code produced a spurious spike here
        gyro = _gyro_after(server, (0, 0, start), (0, 0, end), 1.0)
        assert abs(gyro[2]) == pytest.approx(math.radians(2))
        assert math.copysign(1, gyro[2]) == (1 if start > end else -1)

    def test_yaw_0_to_360_wraparound(self, server):
        gyro = _gyro_after(server, (0, 0, 350), (0, 0, 10), 1.0)
        assert gyro[2] == pytest.approx(math.radians(20))

    def test_stationary_reads_zero(self, server):
        gyro = _gyro_after(server, (10, 20, 30), (10, 20, 30), 1.0)
        assert np.allclose(gyro, 0.0)

    def test_simulation_and_replay_use_the_same_units(self, server):
        # A turn simulated by the emulator and a recording of the same turn
        # made on a real HAT (RTIMULib rad/s) must read back identically
        simulated = _gyro_after(server, (0, 0, 0), (0, 0, 90), 1.0)
        server.set_imu_values(
            accel=(0, 0, 1), gyro=tuple(simulated), compass=(0, 0, 0),
            orientation=(0, 0, 0))
        stored = np.array(server._read().gyro) / GYRO_FACTOR
        assert stored == pytest.approx(tuple(simulated), abs=1 / GYRO_FACTOR)

    def test_factor_matches_lsm9ds1_500dps_range(self):
        # 17.5 mdps per LSB -> 57.14 LSB per dps -> about 3274 LSB per rad/s
        assert GYRO_FACTOR == pytest.approx(3274.06, rel=1e-4)
        assert GYRO_MAX == pytest.approx(math.radians(500))
        # full scale must still fit a signed 16-bit register
        assert GYRO_MAX * GYRO_FACTOR < 32767

    def test_small_rates_keep_their_resolution(self, server):
        # Quantisation step is ~0.0003 rad/s; previously it was ~0.0175 rad/s,
        # so a 0.01 rad/s rate was rounded to zero
        server.set_imu_values(
            accel=(0, 0, 1), gyro=(0.01, -0.02, 0.005), compass=(0, 0, 0),
            orientation=(0, 0, 0))
        stored = np.array(server._read().gyro) / GYRO_FACTOR
        assert stored == pytest.approx((0.01, -0.02, 0.005), abs=1 / GYRO_FACTOR)

    def test_full_scale_is_clamped_to_500_dps(self, server):
        server.set_imu_values(
            accel=(0, 0, 1), gyro=(100.0, -100.0, 0.0), compass=(0, 0, 0),
            orientation=(0, 0, 0))
        stored = np.array(server._read().gyro) / GYRO_FACTOR
        assert stored[0] == pytest.approx(GYRO_MAX, abs=1 / GYRO_FACTOR)
        assert stored[1] == pytest.approx(-GYRO_MAX, abs=1 / GYRO_FACTOR)

    def test_noise_amplitude_is_about_one_dps(self):
        assert GYRO_NOISE == pytest.approx(math.radians(1.0))

    def test_rtimu_reports_radians_per_second(self, server, tmp_imu_file):
        # End to end through the RTIMULib-compatible reader that SenseHat uses
        from sense_emu.RTIMU import Settings, RTIMU
        rtimu = RTIMU(Settings(''))
        try:
            assert rtimu.IMUInit()
            server.set_imu_values(      # newer than what IMUInit() saw
                accel=(0, 0, 1), gyro=(0.5, 0.0, -0.25), compass=(0, 0, 0),
                orientation=(0, 0, 0))
            assert rtimu.IMURead()
            assert rtimu.getGyro() == pytest.approx(
                (0.5, 0.0, -0.25), abs=1 / GYRO_FACTOR)
        finally:
            rtimu._map.close()
            rtimu._fd.close()


# ---------------------------------------------------------------------------
# Timestamps must change on every write, even on a coarse clock (Windows'
# time.monotonic() ticks every ~15.6 ms)
# ---------------------------------------------------------------------------

import threading as _threading                                 # noqa: E402
from unittest.mock import patch as _mock_patch                 # noqa: E402
import sense_emu.imu as _imu_module                            # noqa: E402


class TestTimestampCoarseClock:
    def test_uses_the_high_resolution_clock(self):
        assert _imu_module._time is time.perf_counter

    def test_strictly_increasing_when_the_clock_does_not_advance(self):
        with _mock_patch.object(_imu_module, '_time', lambda: 1.0):
            stamps = [timestamp() for _ in range(50)]
        assert all(b > a for a, b in zip(stamps, stamps[1:]))

    def test_strictly_increasing_when_the_clock_goes_backwards(self):
        readings = iter([10.0, 9.0, 8.0, 12.0])
        with _mock_patch.object(_imu_module, '_time', lambda: next(readings)):
            stamps = [timestamp() for _ in range(4)]
        assert all(b > a for a, b in zip(stamps, stamps[1:]))

    def test_unique_across_threads(self):
        results = []

        def worker():
            results.append([timestamp() for _ in range(2000)])

        threads = [_threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        everything = [ts for chunk in results for ts in chunk]
        assert len(everything) == len(set(everything))
        for chunk in results:                    # each thread sees increasing values
            assert chunk == sorted(chunk)

    def test_reader_sees_an_update_made_within_the_same_clock_tick(self, server, tmp_imu_file):
        # The Windows failure: IMUInit() then set_imu_values() inside one clock
        # tick left the timestamp unchanged, so IMURead() reported "no data".
        from sense_emu.RTIMU import Settings, RTIMU
        rtimu = RTIMU(Settings(''))
        try:
            with _mock_patch.object(_imu_module, '_time', lambda: 1.0):
                assert rtimu.IMUInit()
                server.set_imu_values(
                    accel=(0, 0, 1), gyro=(0.1, 0, 0), compass=(0, 0, 0),
                    orientation=(0, 0, 0))
                assert rtimu.IMURead() is True
                # ... and a second update in the very same tick is also seen
                server.set_imu_values(
                    accel=(0, 0, 1), gyro=(0.2, 0, 0), compass=(0, 0, 0),
                    orientation=(0, 0, 0))
                assert rtimu.IMURead() is True
                assert rtimu.getGyro()[0] == pytest.approx(0.2, abs=1 / GYRO_FACTOR)
                # nothing written since: nothing new
                assert rtimu.IMURead() is False
        finally:
            rtimu._map.close()
            rtimu._fd.close()
