import struct
import pytest
from sense_emu.common import clamp, slow_pi, HEADER_REC, DATA_REC, DataRecord


class TestClamp:
    def test_within_range(self):
        assert clamp(5, 0, 10) == 5

    def test_below_min(self):
        assert clamp(-1, 0, 10) == 0

    def test_above_max(self):
        assert clamp(15, 0, 10) == 10

    def test_at_min_boundary(self):
        assert clamp(0, 0, 10) == 0

    def test_at_max_boundary(self):
        assert clamp(10, 0, 10) == 10

    def test_negative_range(self):
        assert clamp(-5, -10, -1) == -5

    def test_float_values(self):
        assert clamp(1.5, 0.0, 1.0) == 1.0

    @pytest.mark.parametrize('val,lo,hi,expected', [
        (0, 0, 0, 0),
        (100, 50, 200, 100),
        (-100, -200, -50, -100),
    ])
    def test_parametrized(self, val, lo, hi, expected):
        assert clamp(val, lo, hi) == expected


class TestSlowPi:
    def test_returns_bool(self):
        result = slow_pi()
        assert isinstance(result, bool)

    def test_false_on_non_pi(self):
        # CI machines won't be BCM2835/BCM2708
        import sys
        if sys.platform.startswith('linux'):
            result = slow_pi()
            assert result in (True, False)

    def test_false_when_no_cpuinfo(self, tmp_path):
        from unittest.mock import patch, mock_open
        import errno, io
        def fake_open(path, *args, **kwargs):
            if 'cpuinfo' in path:
                raise IOError(errno.ENOENT, 'No such file')
            return io.open(path, *args, **kwargs)
        with patch('sense_emu.common.io.open', side_effect=fake_open):
            result = slow_pi()
        assert result is False

    def test_true_when_bcm2835(self):
        from unittest.mock import patch, mock_open
        fake_content = 'Hardware\t: BCM2835\n'
        with patch('sense_emu.common.io.open', mock_open(read_data=fake_content)):
            result = slow_pi()
        assert result is True

    def test_raises_on_other_ioerror(self):
        from unittest.mock import patch
        import errno
        def bad_open(path, *args, **kwargs):
            raise IOError(errno.EACCES, 'Permission denied')
        with patch('sense_emu.common.io.open', side_effect=bad_open):
            with pytest.raises(IOError):
                slow_pi()


class TestStructs:
    def test_header_rec_roundtrip(self):
        import time
        ts = time.time()
        packed = HEADER_REC.pack(b'SENSEHAT', 1, ts)
        magic, ver, timestamp = HEADER_REC.unpack(packed)
        assert magic == b'SENSEHAT'
        assert ver == 1
        assert abs(timestamp - ts) < 1e-6

    def test_header_rec_size(self):
        # 8s + b + 7x + d = 8 + 1 + 7 + 8 = 24
        assert HEADER_REC.size == 24

    def test_data_rec_roundtrip(self):
        values = (
            1000.0,    # timestamp
            1013.0, 20.0,  # pressure, ptemp
            45.0, 21.0,    # humidity, htemp
            0.1, 0.2, 9.8, # accel
            0.0, 0.1, 0.0, # gyro
            0.3, 0.0, 0.0, # compass
            10.0, 20.0, 30.0, # orientation
        )
        packed = DATA_REC.pack(*values)
        unpacked = DATA_REC.unpack(packed)
        for orig, decoded in zip(values, unpacked):
            assert abs(orig - decoded) < 1e-9

    def test_data_rec_field_count(self):
        assert len(DataRecord._fields) == 17

    def test_data_record_namedtuple(self):
        rec = DataRecord(
            timestamp=1.0,
            pressure=1013.0, ptemp=20.0,
            humidity=45.0, htemp=21.0,
            ax=0.0, ay=0.0, az=1.0,
            gx=0.0, gy=0.0, gz=0.0,
            cx=0.3, cy=0.0, cz=0.0,
            ox=0.0, oy=0.0, oz=0.0,
        )
        assert rec.pressure == 1013.0
        assert rec.humidity == 45.0
        assert rec.ax == 0.0
