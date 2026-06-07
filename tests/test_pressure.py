import math
import time
import pytest
from sense_emu.pressure import PressureServer, PRESSURE_FACTOR, TEMP_FACTOR, TEMP_OFFSET


@pytest.fixture
def server(tmp_pressure_file):
    srv = PressureServer(simulate_noise=False)
    yield srv
    srv.close()


@pytest.fixture
def server_noisy(tmp_pressure_file):
    srv = PressureServer(simulate_noise=True)
    yield srv
    srv.close()


class TestPressureServerBasic:
    def test_default_pressure(self, server):
        assert server.pressure == pytest.approx(1013.0)

    def test_default_temperature(self, server):
        assert server.temperature == pytest.approx(20.0)

    def test_set_values(self, server):
        server.set_values(900.0, 15.0)
        assert server.pressure == pytest.approx(900.0)
        assert server.temperature == pytest.approx(15.0)

    def test_values_written_to_mmap(self, server):
        server.set_values(1000.0, 25.0)
        data = server._read()
        assert data.P_VALID == 1
        assert data.T_VALID == 1
        expected_p = int(1000.0 * PRESSURE_FACTOR)
        expected_t = int((25.0 - TEMP_OFFSET) * TEMP_FACTOR)
        assert abs(data.P_OUT - expected_p) <= 1
        assert abs(data.T_OUT - expected_t) <= 1

    def test_sensor_type_is_set(self, server):
        data = server._read()
        assert data.type == 3

    def test_sensor_name_is_set(self, server):
        data = server._read()
        # '6p' Pascal string holds max 5 chars; b'LPS25H' is truncated to b'LPS25'
        assert b'LPS25' in data.name

    def test_set_values_extreme_min(self, server):
        server.set_values(260.0, -30.0)
        assert server.pressure == pytest.approx(260.0)

    def test_set_values_extreme_max(self, server):
        server.set_values(1260.0, 105.0)
        assert server.pressure == pytest.approx(1260.0)

    def test_close_is_idempotent(self, tmp_pressure_file):
        srv = PressureServer(simulate_noise=False)
        srv.close()
        srv.close()  # second close must not raise


class TestPressureSimulateNoise:
    def test_simulate_noise_default_true(self, tmp_pressure_file):
        srv = PressureServer(simulate_noise=True)
        assert srv.simulate_noise is True
        srv.close()

    def test_simulate_noise_off(self, server):
        assert server.simulate_noise is False

    def test_enable_then_disable_noise(self, server):
        server.simulate_noise = True
        assert server.simulate_noise is True
        time.sleep(0.05)
        server.simulate_noise = False
        assert server.simulate_noise is False

    def test_noise_does_not_drift_too_far(self, server_noisy):
        server_noisy.set_values(1013.0, 20.0)
        time.sleep(0.1)
        data = server_noisy._read()
        # The mean of queued samples must stay within datasheet tolerance
        actual_p = data.P_OUT / PRESSURE_FACTOR
        assert abs(actual_p - 1013.0) < 5.0


class TestPressurePerturb:
    def test_perturb_stays_close(self, server):
        for _ in range(100):
            result = server._perturb(1000.0, 1.0)
            assert abs(result - 1000.0) < 2.0  # ±0.2 * 1.0 Gauss, 3σ ~ 0.6


from unittest.mock import patch
import os
from sense_emu.pressure import (
    pressure_filename, init_pressure, PressureServer,
    PRESSURE_DATA, PressureData, PRESSURE_FACTOR, TEMP_FACTOR, TEMP_OFFSET
)


class TestPressureFilename:
    def test_direct_call_returns_string(self):
        result = pressure_filename()
        assert isinstance(result, str)
        assert 'rpi-sense-emu-pressure' in result

    def test_no_shm_uses_tmp(self):
        with patch('os.path.exists', return_value=False):
            result = pressure_filename()
        assert result == '/tmp/rpi-sense-emu-pressure'

    def test_windows_path(self):
        with patch('sys.platform', 'win32'), \
             patch.dict('os.environ', {'TEMP': '/tmp/wintemp'}):
            result = pressure_filename()
        assert 'rpi-sense-emu-pressure' in result


class TestInitPressure:
    def test_creates_file_when_missing(self, tmp_path):
        path = str(tmp_path / 'new_pressure')
        with patch('sense_emu.pressure.pressure_filename', return_value=path):
            fd = init_pressure()
        assert os.path.exists(path)
        fd.close()


class TestPressureServerAlreadyInitialized:
    def test_reads_existing_type3_data(self, tmp_path):
        path = str(tmp_path / 'pressure')
        pressure = 1013.0
        temperature = 20.0
        p_out = int(pressure * PRESSURE_FACTOR)
        t_out = int((temperature - TEMP_OFFSET) * TEMP_FACTOR)
        data = PressureData(3, b'LPS25', 0, p_out, t_out, 1, 1)
        with open(path, 'wb') as f:
            f.write(PRESSURE_DATA.pack(*data))
        with patch('sense_emu.pressure.pressure_filename', return_value=path):
            server = PressureServer(simulate_noise=False)
        assert server._pressure == pytest.approx(pressure, rel=0.01)
        server.close()
