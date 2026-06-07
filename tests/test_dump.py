import io
import csv
import time
import pytest
from unittest.mock import patch
from sense_emu.dump import DumpApplication
from sense_emu.common import HEADER_REC, DATA_REC


@pytest.fixture
def app():
    return DumpApplication()


class TestDumpSource:
    def test_source_reads_header_and_records(self, app, sample_recording):
        with open(sample_recording, 'rb') as f:
            records = list(app.source(f))
        assert len(records) == 5

    def test_source_invalid_magic_raises(self, app, tmp_path):
        bad = tmp_path / 'bad.bin'
        bad.write_bytes(HEADER_REC.pack(b'BADMAGIC', 1, time.time()))
        with open(bad, 'rb') as f:
            with pytest.raises(IOError, match='Invalid magic'):
                list(app.source(f))

    def test_source_bad_version_raises(self, app, tmp_path):
        bad = tmp_path / 'v2.bin'
        bad.write_bytes(HEADER_REC.pack(b'SENSEHAT', 99, time.time()))
        with open(bad, 'rb') as f:
            with pytest.raises(IOError, match='version'):
                list(app.source(f))

    def test_source_incomplete_record_raises(self, app, tmp_path):
        bad = tmp_path / 'trunc.bin'
        with open(bad, 'wb') as f:
            f.write(HEADER_REC.pack(b'SENSEHAT', 1, time.time()))
            f.write(b'\x00' * (DATA_REC.size - 1))  # incomplete
        with open(bad, 'rb') as f:
            with pytest.raises(IOError, match='Incomplete'):
                list(app.source(f))

    def test_record_fields_count(self, app, sample_recording):
        with open(sample_recording, 'rb') as f:
            records = list(app.source(f))
        assert len(records[0]) == 17


class TestDumpMain:
    def test_generates_csv_rows(self, app, sample_recording, tmp_path):
        out_file = str(tmp_path / 'out.csv')
        app([sample_recording, out_file])
        with open(out_file, 'r', newline='') as f:
            rows = [r for r in csv.reader(f) if r]  # Filter empty rows
        assert len(rows) >= 4  # At least 4 data rows

    def test_header_flag_adds_header_row(self, app, sample_recording, tmp_path):
        out_file = str(tmp_path / 'out.csv')
        app(['--header', sample_recording, out_file])
        with open(out_file, 'r', newline='') as f:
            rows = [r for r in csv.reader(f) if r]  # Filter empty rows
        assert rows[0][0] == 'timestamp'
        assert len(rows) >= 5  # At least 1 header + 4 data

    def test_csv_has_correct_column_count(self, app, sample_recording, tmp_path):
        out_file = str(tmp_path / 'out.csv')
        app(['--header', sample_recording, out_file])
        with open(out_file, 'r', newline='') as f:
            rows = [r for r in csv.reader(f) if r]  # Filter empty rows
        assert all(len(row) == 17 for row in rows)

    def test_custom_timestamp_format(self, app, sample_recording, tmp_path):
        import sys
        out_file = str(tmp_path / 'out.csv')
        # Use %Y-%m-%d format instead of %s which is not supported on Windows
        timestamp_format = '%Y-%m-%d' if sys.platform.startswith('win') else '%s'
        app(['--timestamp-format', timestamp_format, sample_recording, out_file])
        with open(out_file, 'r', newline='') as f:
            rows = [r for r in csv.reader(f) if r]  # Filter empty rows
        # Verify we have at least one row with data
        assert len(rows) >= 1

    def test_pressure_values_match_input(self, app, sample_recording, tmp_path):
        out_file = str(tmp_path / 'out.csv')
        app([sample_recording, out_file])
        with open(out_file, 'r') as f:
            rows = list(csv.reader(f))
        # First row: pressure starts at 1013.0
        assert abs(float(rows[0][1]) - 1013.0) < 0.01

    def test_output_to_stdout(self, app, sample_recording):
        import io
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            app([sample_recording, '-'])
