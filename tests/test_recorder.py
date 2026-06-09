import time
import threading
import pytest
from unittest.mock import patch, MagicMock

from sense_emu.recorder import Recorder
from sense_emu.recfile import parse_recording


class TestRecorderUnit:
    """Unit tests using mocked RTIMU module."""

    def _make_mock_rtimu_mod(self):
        mod = MagicMock()
        settings = MagicMock()
        mod.Settings.return_value = settings

        imu = MagicMock()
        imu.IMUInit.return_value = True
        imu.IMUGetPollInterval.return_value = 10
        call_count = [0]
        def imu_read():
            call_count[0] += 1
            return call_count[0] % 2 == 1  # True on odd calls
        imu.IMURead.side_effect = imu_read
        imu.getAccel.return_value = (0.0, 0.0, 1.0)
        imu.getGyro.return_value = (0.0, 0.0, 0.0)
        imu.getCompass.return_value = (0.0, 0.0, 0.0)
        imu.getFusionData.return_value = (0.0, 0.0, 0.0)
        mod.RTIMU.return_value = imu

        psensor = MagicMock()
        psensor.pressureInit.return_value = True
        psensor.pressureRead.return_value = (True, 1013.0, True, 20.0)
        mod.RTPressure.return_value = psensor

        hsensor = MagicMock()
        hsensor.humidityInit.return_value = True
        hsensor.humidityRead.return_value = (True, 45.0, True, 21.0)
        mod.RTHumidity.return_value = hsensor

        return mod

    def test_initial_state(self, tmp_path):
        r = Recorder(str(tmp_path / 'out.bin'))
        assert not r.running
        assert r.record_count == 0

    def test_start_sets_running(self, tmp_path):
        mod = self._make_mock_rtimu_mod()
        with patch('sense_emu.recorder._rtimu_mod', mod):
            r = Recorder(str(tmp_path / 'out.bin'), interval=0.01)
            r.start()
            assert r.running
            r.stop()

    def test_stop_clears_running(self, tmp_path):
        mod = self._make_mock_rtimu_mod()
        with patch('sense_emu.recorder._rtimu_mod', mod):
            r = Recorder(str(tmp_path / 'out.bin'), interval=0.01)
            r.start()
            r.stop()
            assert not r.running

    def test_double_start_noop(self, tmp_path):
        mod = self._make_mock_rtimu_mod()
        with patch('sense_emu.recorder._rtimu_mod', mod):
            r = Recorder(str(tmp_path / 'out.bin'), interval=0.5)
            r.start()
            old_thread = r._thread
            r.start()  # second call while running
            assert r._thread is old_thread
            r.stop()

    def test_records_written_to_file(self, tmp_path):
        mod = self._make_mock_rtimu_mod()
        path = str(tmp_path / 'out.bin')
        with patch('sense_emu.recorder._rtimu_mod', mod):
            r = Recorder(path, interval=0.01)
            r.start()
            time.sleep(0.15)
            r.stop()
        assert r.record_count >= 1
        records = parse_recording(path)
        assert len(records) >= 1
        assert records[0].pressure == pytest.approx(1013.0)
        assert records[0].humidity == pytest.approx(45.0)

    def test_file_has_correct_header(self, tmp_path):
        mod = self._make_mock_rtimu_mod()
        path = str(tmp_path / 'out.bin')
        with patch('sense_emu.recorder._rtimu_mod', mod):
            r = Recorder(path, interval=0.5)
            r.start()
            time.sleep(0.05)
            r.stop()
        # parse_recording will raise ValueError if header is wrong
        parse_recording(path)  # must not raise

    def test_stop_interrupts_quickly(self, tmp_path):
        mod = self._make_mock_rtimu_mod()
        with patch('sense_emu.recorder._rtimu_mod', mod):
            r = Recorder(str(tmp_path / 'out.bin'), interval=10.0)
            r.start()
            t0 = time.time()
            r.stop()
            assert time.time() - t0 < 1.0
