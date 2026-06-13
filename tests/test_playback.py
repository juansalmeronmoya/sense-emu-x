import threading
import time
import struct
import pytest
from unittest.mock import MagicMock, patch

from sense_emu.playback import Player
from sense_emu.common import HEADER_REC, DATA_REC


def _write_recording(path, n_records=3, delta=0.05):
    """Write a recording with fast deltas so tests run quickly."""
    with open(str(path), 'wb') as f:
        t0 = time.time()
        f.write(HEADER_REC.pack(b'SENSEHAT', 1, t0))
        for i in range(n_records):
            f.write(DATA_REC.pack(
                t0 + i * delta,
                1013.0 + i, 20.0,   # pressure, ptemp
                45.0 + i, 21.0,     # humidity, htemp
                0.0, 0.0, 1.0,      # ax, ay, az
                0.0, 0.0, 0.0,      # gx, gy, gz
                0.0, 0.0, 0.0,      # cx, cy, cz
                float(i), 0.0, 0.0, # ox, oy, oz
            ))
    return str(path)


def _make_mock_servers():
    imu = MagicMock()
    imu.simulate_world = False
    pressure = MagicMock()
    pressure.simulate_noise = False
    humidity = MagicMock()
    humidity.simulate_noise = False
    return imu, pressure, humidity


class TestPlayerInit:
    def test_initial_state(self):
        imu, pressure, humidity = _make_mock_servers()
        player = Player(imu, pressure, humidity)
        assert not player.running
        assert player.progress == 0.0
        assert player.position == 0
        assert player.total == 0
        assert player.current is None

    def test_empty_recording_noop(self, tmp_path):
        imu, pressure, humidity = _make_mock_servers()
        player = Player(imu, pressure, humidity)
        # Write a valid header but no records
        path = str(tmp_path / 'empty.bin')
        with open(path, 'wb') as f:
            f.write(HEADER_REC.pack(b'SENSEHAT', 1, time.time()))
        player.play(path)
        assert not player.running
        assert player.total == 0


class TestPlayerPlay:
    def test_play_sets_running(self, tmp_path):
        imu, pressure, humidity = _make_mock_servers()
        player = Player(imu, pressure, humidity)
        path = _write_recording(tmp_path / 'rec.bin', n_records=5, delta=0.05)
        player.play(path)
        assert player.total == 5
        player.stop()

    def test_play_injects_values(self, tmp_path):
        imu, pressure, humidity = _make_mock_servers()
        player = Player(imu, pressure, humidity)
        path = _write_recording(tmp_path / 'rec.bin', n_records=3, delta=0.02)
        player.play(path)
        done = threading.Event()
        def wait():
            while player.running:
                time.sleep(0.01)
            done.set()
        threading.Thread(target=wait, daemon=True).start()
        done.wait(timeout=2.0)
        assert pressure.set_values.call_count >= 1
        assert humidity.set_values.call_count >= 1
        assert imu.set_imu_values.call_count >= 1

    def test_progress_reaches_one(self, tmp_path):
        imu, pressure, humidity = _make_mock_servers()
        player = Player(imu, pressure, humidity)
        path = _write_recording(tmp_path / 'rec.bin', n_records=3, delta=0.01)
        player.play(path)
        deadline = time.time() + 3.0
        while player.running and time.time() < deadline:
            time.sleep(0.02)
        assert not player.running
        assert player.progress == pytest.approx(1.0)

    def test_stop_interrupts_quickly(self, tmp_path):
        imu, pressure, humidity = _make_mock_servers()
        player = Player(imu, pressure, humidity)
        path = _write_recording(tmp_path / 'rec.bin', n_records=100, delta=0.5)
        player.play(path)
        t0 = time.time()
        player.stop()
        assert time.time() - t0 < 0.5
        assert not player.running

    def test_flags_restored_after_play(self, tmp_path):
        imu, pressure, humidity = _make_mock_servers()
        imu.simulate_world = True
        pressure.simulate_noise = True
        humidity.simulate_noise = True
        player = Player(imu, pressure, humidity)
        path = _write_recording(tmp_path / 'rec.bin', n_records=2, delta=0.01)
        player.play(path)
        deadline = time.time() + 3.0
        while player.running and time.time() < deadline:
            time.sleep(0.02)
        assert imu.simulate_world is True
        assert pressure.simulate_noise is True
        assert humidity.simulate_noise is True

    def test_flags_restored_after_stop(self, tmp_path):
        imu, pressure, humidity = _make_mock_servers()
        imu.simulate_world = True
        pressure.simulate_noise = True
        humidity.simulate_noise = True
        player = Player(imu, pressure, humidity)
        path = _write_recording(tmp_path / 'rec.bin', n_records=50, delta=0.5)
        player.play(path)
        time.sleep(0.05)
        player.stop()
        assert imu.simulate_world is True
        assert pressure.simulate_noise is True
        assert humidity.simulate_noise is True

    def test_current_updates_during_play(self, tmp_path):
        imu, pressure, humidity = _make_mock_servers()
        player = Player(imu, pressure, humidity)
        path = _write_recording(tmp_path / 'rec.bin', n_records=5, delta=0.01)
        player.play(path)
        deadline = time.time() + 3.0
        while player.running and time.time() < deadline:
            time.sleep(0.02)
        assert player.current is not None

    def test_double_play_ignored(self, tmp_path):
        imu, pressure, humidity = _make_mock_servers()
        player = Player(imu, pressure, humidity)
        path = _write_recording(tmp_path / 'rec.bin', n_records=50, delta=0.5)
        player.play(path)
        assert player.running
        old_thread = player._thread
        player.play(path)  # second call while running — should be a no-op
        assert player._thread is old_thread
        player.stop()

    def test_invalid_file_raises(self, tmp_path):
        imu, pressure, humidity = _make_mock_servers()
        player = Player(imu, pressure, humidity)
        bad = str(tmp_path / 'bad.bin')
        with open(bad, 'wb') as f:
            f.write(b'\x00' * 8)
        with pytest.raises(ValueError):
            player.play(bad)
        assert not player.running
