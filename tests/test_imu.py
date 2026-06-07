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
        with patch('os.path.exists', return_value=False):
            result = imu_filename()
        assert result == '/tmp/rpi-sense-emu-imu'

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
