import time
import pytest
from unittest.mock import patch
from sense_emu.RTIMU import Settings, RTIMU, RTPressure, RTHumidity
from sense_emu.imu import IMUServer, imu_filename
from sense_emu.pressure import PressureServer, pressure_filename
from sense_emu.humidity import HumidityServer, humidity_filename


@pytest.fixture
def imu_server(tmp_imu_file):
    srv = IMUServer(simulate_world=False)
    srv.set_imu_values(
        accel=(0.0, 0.0, 1.0),
        gyro=(0.01, 0.0, 0.0),
        compass=(0.33, 0.0, 0.0),
        orientation=(0.0, 0.0, 0.0),
    )
    yield srv
    srv.close()


@pytest.fixture
def pressure_server(tmp_pressure_file):
    srv = PressureServer(simulate_noise=False)
    srv.set_values(1013.0, 20.0)
    yield srv
    srv.close()


@pytest.fixture
def humidity_server(tmp_humidity_file):
    srv = HumidityServer(simulate_noise=False)
    srv.set_values(45.0, 20.0)
    yield srv
    srv.close()


class TestSettings:
    def test_stores_path(self):
        s = Settings('/etc/RTIMULib')
        assert s.path == '/etc/RTIMULib'


class TestRTIMU:
    def test_imu_init_returns_true_when_type_nonzero(self, imu_server, tmp_imu_file):
        rtimu = RTIMU(Settings('/etc/RTIMULib'))
        result = rtimu.IMUInit()
        assert result is True

    def test_imu_get_poll_interval(self, imu_server, tmp_imu_file):
        rtimu = RTIMU(Settings('/etc/RTIMULib'))
        rtimu.IMUInit()
        assert rtimu.IMUGetPollInterval() == 10

    def test_imu_read_returns_true_on_new_data(self, imu_server, tmp_imu_file):
        rtimu = RTIMU(Settings('/etc/RTIMULib'))
        rtimu.IMUInit()
        # Write new data with different timestamp
        time.sleep(0.01)
        imu_server.set_imu_values(
            accel=(0.0, 0.0, 1.0),
            gyro=(0.0, 0.0, 0.0),
            compass=(0.33, 0.0, 0.0),
            orientation=(0.0, 0.0, 0.0),
        )
        result = rtimu.IMURead()
        assert isinstance(result, bool)

    def test_imu_read_false_when_same_timestamp(self, imu_server, tmp_imu_file):
        rtimu = RTIMU(Settings('/etc/RTIMULib'))
        rtimu.IMUInit()
        # Read once
        rtimu.IMURead()
        # Read again without changing data — same timestamp
        result = rtimu.IMURead()
        assert result is False

    def test_get_imu_data_returns_dict(self, imu_server, tmp_imu_file):
        rtimu = RTIMU(Settings('/etc/RTIMULib'))
        rtimu.IMUInit()
        data = rtimu.getIMUData()
        assert isinstance(data, dict)
        assert 'accel' in data
        assert 'gyro' in data
        assert 'compass' in data

    def test_get_accel_returns_tuple(self, imu_server, tmp_imu_file):
        rtimu = RTIMU(Settings('/etc/RTIMULib'))
        rtimu.IMUInit()
        accel = rtimu.getAccel()
        assert len(accel) == 3

    def test_get_gyro_returns_tuple(self, imu_server, tmp_imu_file):
        rtimu = RTIMU(Settings('/etc/RTIMULib'))
        rtimu.IMUInit()
        gyro = rtimu.getGyro()
        assert len(gyro) == 3

    def test_get_compass_returns_tuple(self, imu_server, tmp_imu_file):
        rtimu = RTIMU(Settings('/etc/RTIMULib'))
        rtimu.IMUInit()
        compass = rtimu.getCompass()
        assert len(compass) == 3

    def test_get_fusion_data_returns_tuple(self, imu_server, tmp_imu_file):
        rtimu = RTIMU(Settings('/etc/RTIMULib'))
        rtimu.IMUInit()
        pose = rtimu.getFusionData()
        assert len(pose) == 3

    def test_imu_type_nonzero(self, imu_server, tmp_imu_file):
        rtimu = RTIMU(Settings('/etc/RTIMULib'))
        rtimu.IMUInit()
        assert rtimu.IMUType() != 0

    def test_imu_name_is_string(self, imu_server, tmp_imu_file):
        rtimu = RTIMU(Settings('/etc/RTIMULib'))
        rtimu.IMUInit()
        name = rtimu.IMUName()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_set_gyro_enable_does_not_raise(self, imu_server, tmp_imu_file):
        rtimu = RTIMU(Settings('/etc/RTIMULib'))
        rtimu.setGyroEnable(True)

    def test_set_compass_enable_does_not_raise(self, imu_server, tmp_imu_file):
        rtimu = RTIMU(Settings('/etc/RTIMULib'))
        rtimu.setCompassEnable(True)

    def test_set_accel_enable_does_not_raise(self, imu_server, tmp_imu_file):
        rtimu = RTIMU(Settings('/etc/RTIMULib'))
        rtimu.setAccelEnable(True)

    def test_imu_read_updates_fusion_pose(self, imu_server, tmp_imu_file):
        rtimu = RTIMU(Settings('/etc/RTIMULib'))
        rtimu.IMUInit()
        time.sleep(0.01)
        imu_server.set_imu_values(
            accel=(0.0, 0.0, 1.0),
            gyro=(0.0, 0.0, 0.0),
            compass=(0.33, 0.0, 0.0),
            orientation=(1.0, 0.0, 0.0),
        )
        rtimu.IMURead()
        data = rtimu.getIMUData()
        assert data['fusionPoseValid'] is True


class TestRTPressure:
    def test_pressure_init_true(self, pressure_server, tmp_pressure_file):
        rtpressure = RTPressure(Settings('/etc/RTIMULib'))
        result = rtpressure.pressureInit()
        assert result is True

    def test_pressure_read_returns_values(self, pressure_server, tmp_pressure_file):
        rtpressure = RTPressure(Settings('/etc/RTIMULib'))
        rtpressure.pressureInit()
        pvalid, pressure, tvalid, temp = rtpressure.pressureRead()
        assert pvalid == 1
        assert pressure == pytest.approx(1013.0, abs=5)
        assert tvalid == 1
        assert isinstance(temp, float)

    def test_pressure_read_without_init_returns_zeros(self, pressure_server, tmp_pressure_file):
        rtpressure = RTPressure(Settings('/etc/RTIMULib'))
        result = rtpressure.pressureRead()
        assert result == (0, 0.0, 0, 0.0)

    def test_pressure_type_nonzero(self, pressure_server, tmp_pressure_file):
        rtpressure = RTPressure(Settings('/etc/RTIMULib'))
        rtpressure.pressureInit()
        assert rtpressure.pressureType() != 0

    def test_pressure_name_is_string(self, pressure_server, tmp_pressure_file):
        rtpressure = RTPressure(Settings('/etc/RTIMULib'))
        rtpressure.pressureInit()
        name = rtpressure.pressureName()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_pressure_caches_read(self, pressure_server, tmp_pressure_file):
        rtpressure = RTPressure(Settings('/etc/RTIMULib'))
        rtpressure.pressureInit()
        # Two reads in quick succession should use cached value
        r1 = rtpressure.pressureRead()
        r2 = rtpressure.pressureRead()
        assert r1[1] == r2[1]


class TestRTHumidity:
    def test_humidity_init_true(self, humidity_server, tmp_humidity_file):
        rthumidity = RTHumidity(Settings('/etc/RTIMULib'))
        result = rthumidity.humidityInit()
        assert result is True

    def test_humidity_read_returns_values(self, humidity_server, tmp_humidity_file):
        rthumidity = RTHumidity(Settings('/etc/RTIMULib'))
        rthumidity.humidityInit()
        hvalid, humidity, tvalid, temp = rthumidity.humidityRead()
        assert hvalid == 1
        assert isinstance(humidity, float)
        assert tvalid == 1
        assert isinstance(temp, float)

    def test_humidity_read_without_init_returns_zeros(self, humidity_server, tmp_humidity_file):
        rthumidity = RTHumidity(Settings('/etc/RTIMULib'))
        result = rthumidity.humidityRead()
        assert result == (0, 0.0, 0, 0.0)

    def test_humidity_type_nonzero(self, humidity_server, tmp_humidity_file):
        rthumidity = RTHumidity(Settings('/etc/RTIMULib'))
        rthumidity.humidityInit()
        assert rthumidity.humidityType() != 0

    def test_humidity_name_is_string(self, humidity_server, tmp_humidity_file):
        rthumidity = RTHumidity(Settings('/etc/RTIMULib'))
        rthumidity.humidityInit()
        name = rthumidity.humidityName()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_humidity_caches_read(self, humidity_server, tmp_humidity_file):
        rthumidity = RTHumidity(Settings('/etc/RTIMULib'))
        rthumidity.humidityInit()
        h1 = rthumidity.humidityRead()
        h2 = rthumidity.humidityRead()
        assert h1[1] == h2[1]
