import time
import pytest
from sense_emu.humidity import HumidityServer, HUMIDITY_FACTOR, TEMP_FACTOR


@pytest.fixture
def server(tmp_humidity_file):
    srv = HumidityServer(simulate_noise=False)
    yield srv
    srv.close()


@pytest.fixture
def server_noisy(tmp_humidity_file):
    srv = HumidityServer(simulate_noise=True)
    yield srv
    srv.close()


class TestHumidityServerBasic:
    def test_default_humidity(self, server):
        assert server.humidity == pytest.approx(45.0)

    def test_default_temperature(self, server):
        assert server.temperature == pytest.approx(20.0)

    def test_set_values(self, server):
        server.set_values(70.0, 30.0)
        assert server.humidity == pytest.approx(70.0)
        assert server.temperature == pytest.approx(30.0)

    def test_values_written_to_mmap(self, server):
        server.set_values(60.0, 22.0)
        data = server._read()
        assert data.H_VALID == 1
        assert data.T_VALID == 1
        expected_h = int(60.0 * HUMIDITY_FACTOR)
        expected_t = int(22.0 * TEMP_FACTOR)
        assert abs(data.H_OUT - expected_h) <= 1
        assert abs(data.T_OUT - expected_t) <= 1

    def test_sensor_type_is_set(self, server):
        data = server._read()
        assert data.type == 2

    def test_sensor_name_is_set(self, server):
        data = server._read()
        # '6p' Pascal string holds max 5 chars; b'HTS221' is truncated to b'HTS22'
        assert b'HTS22' in data.name

    def test_extreme_humidity_min(self, server):
        server.set_values(0.0, -40.0)
        assert server.humidity == pytest.approx(0.0)

    def test_extreme_humidity_max(self, server):
        server.set_values(100.0, 120.0)
        assert server.humidity == pytest.approx(100.0)

    def test_close_is_idempotent(self, tmp_humidity_file):
        srv = HumidityServer(simulate_noise=False)
        srv.close()
        srv.close()


class TestHumiditySimulateNoise:
    def test_noise_off_by_default_fixture(self, server):
        assert server.simulate_noise is False

    def test_noise_on(self, tmp_humidity_file):
        srv = HumidityServer(simulate_noise=True)
        assert srv.simulate_noise is True
        srv.close()

    def test_enable_then_disable_noise(self, server):
        server.simulate_noise = True
        assert server.simulate_noise is True
        time.sleep(0.15)
        server.simulate_noise = False
        assert server.simulate_noise is False

    def test_noise_stays_within_tolerance(self, server_noisy):
        server_noisy.set_values(50.0, 25.0)
        time.sleep(0.15)
        data = server_noisy._read()
        actual_h = data.H_OUT / HUMIDITY_FACTOR
        assert abs(actual_h - 50.0) < 10.0


class TestHumidityPerturb:
    def test_perturb_returns_close_value(self, server):
        for _ in range(50):
            result = server._perturb(50.0, 1.0)
            assert abs(result - 50.0) < 2.0


from unittest.mock import patch
import os
from sense_emu.humidity import (
    humidity_filename, init_humidity, HumidityServer,
    HUMIDITY_DATA, HumidityData, HUMIDITY_FACTOR, TEMP_FACTOR
)


class TestHumidityFilename:
    def test_direct_call_returns_string(self):
        result = humidity_filename()
        assert isinstance(result, str)
        assert 'rpi-sense-emu-humidity' in result

    def test_no_shm_uses_tmp(self):
        with patch('os.path.exists', return_value=False):
            result = humidity_filename()
        assert result == '/tmp/rpi-sense-emu-humidity'

    def test_windows_path(self):
        with patch('sys.platform', 'win32'), \
             patch.dict('os.environ', {'TEMP': '/tmp/wintemp'}):
            result = humidity_filename()
        assert 'rpi-sense-emu-humidity' in result


class TestInitHumidity:
    def test_creates_file_when_missing(self, tmp_path):
        path = str(tmp_path / 'new_humidity')
        with patch('sense_emu.humidity.humidity_filename', return_value=path):
            fd = init_humidity()
        assert os.path.exists(path)
        fd.close()


class TestHumidityServerAlreadyInitialized:
    def test_reads_existing_type2_data(self, tmp_path):
        path = str(tmp_path / 'humidity')
        # Write a file already initialized with type=2 and valid data
        data = HumidityData(2, b'HTS22', 0, 100, 0, 100, 0, 25600, 0, 6400,
                            int(45.0 * HUMIDITY_FACTOR), int(20.0 * TEMP_FACTOR), 1, 1)
        with open(path, 'wb') as f:
            f.write(HUMIDITY_DATA.pack(*data))
        with patch('sense_emu.humidity.humidity_filename', return_value=path):
            server = HumidityServer(simulate_noise=False)
        assert server._humidity == pytest.approx(45.0, abs=1.0)
        server.close()
