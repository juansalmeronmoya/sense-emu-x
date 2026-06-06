import io
import sys
import types
import argparse
import pytest
from unittest.mock import patch, MagicMock


class _UnclosableBuffer(io.BytesIO):
    """BytesIO that ignores close() calls, so we can read after main() finishes."""
    def close(self):
        pass


def _make_rtimu_mock():
    mock_settings = MagicMock()
    mock_imu = MagicMock()
    mock_imu.IMUInit.return_value = True
    mock_imu.IMURead.return_value = True
    mock_imu.IMUGetPollInterval.return_value = 3
    mock_imu.getAccel.return_value = (0.0, 0.0, 1.0)
    mock_imu.getGyro.return_value = (0.0, 0.0, 0.0)
    mock_imu.getCompass.return_value = (0.33, 0.0, 0.0)
    mock_imu.getFusionData.return_value = (0.0, 0.0, 0.0)

    mock_pressure = MagicMock()
    mock_pressure.pressureInit.return_value = True
    mock_pressure.pressureRead.return_value = (True, 1013.0, True, 20.0)

    mock_humidity = MagicMock()
    mock_humidity.humidityInit.return_value = True
    mock_humidity.humidityRead.return_value = (True, 45.0, True, 20.0)

    rtimu_mod = MagicMock()
    rtimu_mod.Settings.return_value = mock_settings
    rtimu_mod.RTIMU.return_value = mock_imu
    rtimu_mod.RTPressure.return_value = mock_pressure
    rtimu_mod.RTHumidity.return_value = mock_humidity
    return rtimu_mod


@pytest.fixture
def rtimu_mock():
    return _make_rtimu_mock()


class _Namespace:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class TestRecordApplicationMain:
    def test_records_to_bytesio(self, rtimu_mock):
        from sense_emu.record import RecordApplication
        from sense_emu.common import HEADER_REC, DATA_REC
        output = _UnclosableBuffer()
        args = _Namespace(
            config='RTIMULib.ini',
            interval=0.0,
            duration=0.01,
            flush=False,
            output=output,
        )
        with patch.dict('sys.modules', {'RTIMU': rtimu_mock}):
            app = RecordApplication()
            app.main(args)
        output.seek(0)
        header_bytes = output.read(HEADER_REC.size)
        assert header_bytes[:8] == b'SENSEHAT'

    def test_records_at_least_one_data_rec(self, rtimu_mock):
        from sense_emu.record import RecordApplication
        from sense_emu.common import HEADER_REC, DATA_REC
        output = _UnclosableBuffer()
        args = _Namespace(
            config='RTIMULib.ini',
            interval=0.0,
            duration=0.05,
            flush=False,
            output=output,
        )
        with patch.dict('sys.modules', {'RTIMU': rtimu_mock}):
            app = RecordApplication()
            app.main(args)
        output.seek(0)
        data = output.read()
        total = len(data)
        assert total >= HEADER_REC.size + DATA_REC.size

    def test_flush_flag(self, rtimu_mock):
        from sense_emu.record import RecordApplication
        output = _UnclosableBuffer()
        args = _Namespace(
            config='RTIMULib.ini',
            interval=0.0,
            duration=0.01,
            flush=True,
            output=output,
        )
        with patch.dict('sys.modules', {'RTIMU': rtimu_mock}):
            app = RecordApplication()
            app.main(args)  # should not raise

    def test_interval_none_uses_poll_interval(self, rtimu_mock):
        from sense_emu.record import RecordApplication
        output = _UnclosableBuffer()
        args = _Namespace(
            config='RTIMULib.ini',
            interval=None,
            duration=0.01,
            flush=False,
            output=output,
        )
        with patch.dict('sys.modules', {'RTIMU': rtimu_mock}):
            app = RecordApplication()
            app.main(args)
        # Interval should have been set from poll interval: 3/1000.0 = 0.003
        assert args.interval == pytest.approx(0.003)

    def test_imu_read_false_skips_record(self, rtimu_mock):
        from sense_emu.record import RecordApplication
        from sense_emu.common import HEADER_REC, DATA_REC
        rtimu_mock.RTIMU.return_value.IMURead.return_value = False
        output = _UnclosableBuffer()
        args = _Namespace(
            config='RTIMULib.ini',
            interval=0.0,
            duration=0.01,
            flush=False,
            output=output,
        )
        with patch.dict('sys.modules', {'RTIMU': rtimu_mock}):
            app = RecordApplication()
            app.main(args)
        output.seek(0)
        data = output.read()
        # Only header, no data records
        assert len(data) == HEADER_REC.size

    def test_pressure_invalid_uses_nan(self, rtimu_mock):
        from sense_emu.record import RecordApplication
        from sense_emu.common import HEADER_REC, DATA_REC
        import struct, math
        rtimu_mock.RTPressure.return_value.pressureRead.return_value = (False, 0.0, False, 0.0)
        output = _UnclosableBuffer()
        args = _Namespace(
            config='RTIMULib.ini',
            interval=0.0,
            duration=0.01,
            flush=False,
            output=output,
        )
        with patch.dict('sys.modules', {'RTIMU': rtimu_mock}):
            app = RecordApplication()
            app.main(args)
        output.seek(HEADER_REC.size)
        rec_bytes = output.read(DATA_REC.size)
        if rec_bytes:
            vals = DATA_REC.unpack(rec_bytes)
            assert math.isnan(vals[1])  # pressure NaN

    def test_missing_rtimu_raises(self):
        from sense_emu.record import RecordApplication
        output = _UnclosableBuffer()
        args = _Namespace(
            config='RTIMULib.ini',
            interval=0.0,
            duration=0.01,
            flush=False,
            output=output,
        )
        # Remove RTIMU from sys.modules so import fails
        with patch.dict('sys.modules', {'RTIMU': None}):
            app = RecordApplication()
            with pytest.raises((IOError, ImportError)):
                app.main(args)

    def test_bad_config_extension_raises(self, rtimu_mock):
        from sense_emu.record import RecordApplication
        output = _UnclosableBuffer()
        args = _Namespace(
            config='RTIMULib.cfg',  # wrong extension
            interval=0.0,
            duration=0.01,
            flush=False,
            output=output,
        )
        with patch.dict('sys.modules', {'RTIMU': rtimu_mock}):
            app = RecordApplication()
            with pytest.raises((argparse.ArgumentError, Exception)):
                app.main(args)

    def test_imu_init_failure_raises(self, rtimu_mock):
        from sense_emu.record import RecordApplication
        rtimu_mock.RTIMU.return_value.IMUInit.return_value = False
        output = _UnclosableBuffer()
        args = _Namespace(
            config='RTIMULib.ini',
            interval=0.0,
            duration=0.01,
            flush=False,
            output=output,
        )
        with patch.dict('sys.modules', {'RTIMU': rtimu_mock}):
            app = RecordApplication()
            with pytest.raises(IOError):
                app.main(args)

    def test_pressure_init_failure_raises(self, rtimu_mock):
        from sense_emu.record import RecordApplication
        rtimu_mock.RTPressure.return_value.pressureInit.return_value = False
        output = _UnclosableBuffer()
        args = _Namespace(
            config='RTIMULib.ini',
            interval=0.0,
            duration=0.01,
            flush=False,
            output=output,
        )
        with patch.dict('sys.modules', {'RTIMU': rtimu_mock}):
            app = RecordApplication()
            with pytest.raises(IOError):
                app.main(args)

    def test_humidity_init_failure_raises(self, rtimu_mock):
        from sense_emu.record import RecordApplication
        rtimu_mock.RTHumidity.return_value.humidityInit.return_value = False
        output = _UnclosableBuffer()
        args = _Namespace(
            config='RTIMULib.ini',
            interval=0.0,
            duration=0.01,
            flush=False,
            output=output,
        )
        with patch.dict('sys.modules', {'RTIMU': rtimu_mock}):
            app = RecordApplication()
            with pytest.raises(IOError):
                app.main(args)
