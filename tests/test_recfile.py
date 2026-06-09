import struct
import time
import pytest
from sense_emu.recfile import parse_recording, _parse_recording
from sense_emu.common import HEADER_REC, DATA_REC


def _write_recording(path, n_records=3):
    """Write a minimal valid recording file with n_records entries."""
    with open(path, 'wb') as f:
        f.write(HEADER_REC.pack(b'SENSEHAT', 1, time.time()))
        for i in range(n_records):
            f.write(DATA_REC.pack(
                time.time() + i * 0.1,  # timestamp
                1013.0, 20.0,           # pressure, ptemp
                45.0, 21.0,             # humidity, htemp
                0.0, 0.0, 1.0,          # ax, ay, az
                0.0, 0.0, 0.0,          # gx, gy, gz
                0.0, 0.0, 0.0,          # cx, cy, cz
                0.0, 0.0, 0.0,          # ox, oy, oz
            ))
    return str(path)


class TestParseRecording:
    def test_returns_correct_count(self, tmp_path):
        path = _write_recording(tmp_path / 'rec.bin', n_records=4)
        records = parse_recording(path)
        assert len(records) == 4

    def test_values_are_correct(self, tmp_path):
        path = _write_recording(tmp_path / 'rec.bin', n_records=1)
        records = parse_recording(path)
        assert records[0].pressure == pytest.approx(1013.0)
        assert records[0].humidity == pytest.approx(45.0)
        assert records[0].az == pytest.approx(1.0)

    def test_timestamps_increase(self, tmp_path):
        path = _write_recording(tmp_path / 'rec.bin', n_records=3)
        records = parse_recording(path)
        for i in range(1, len(records)):
            assert records[i].timestamp > records[i - 1].timestamp

    def test_invalid_magic_raises(self, tmp_path):
        bad = tmp_path / 'bad.bin'
        bad.write_bytes(b'\x00' * 64)
        with pytest.raises(ValueError, match='Invalid'):
            parse_recording(str(bad))

    def test_wrong_magic_string_raises(self, tmp_path):
        bad = tmp_path / 'bad.bin'
        bad.write_bytes(HEADER_REC.pack(b'WRONGMAG', 1, time.time()))
        with pytest.raises(ValueError, match='Invalid'):
            parse_recording(str(bad))

    def test_truncated_record_raises(self, tmp_path):
        path = tmp_path / 'trunc.bin'
        with open(path, 'wb') as f:
            f.write(HEADER_REC.pack(b'SENSEHAT', 1, time.time()))
            f.write(b'\x00' * (DATA_REC.size - 1))  # one byte short
        with pytest.raises(ValueError, match='Truncated'):
            parse_recording(str(path))

    def test_empty_recording_returns_empty_list(self, tmp_path):
        path = tmp_path / 'empty.bin'
        with open(path, 'wb') as f:
            f.write(HEADER_REC.pack(b'SENSEHAT', 1, time.time()))
        assert parse_recording(str(path)) == []

    def test_alias_is_same_function(self):
        assert _parse_recording is parse_recording
