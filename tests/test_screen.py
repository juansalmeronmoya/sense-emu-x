import os
import struct
import time
import pytest
import numpy as np
from sense_emu.screen import ScreenClient, screen_filename, GAMMA_DEFAULT, GAMMA_LOW


@pytest.fixture
def client(tmp_screen_file):
    c = ScreenClient()
    yield c
    c.close()


class TestScreenFilename:
    def test_returns_string(self):
        fname = screen_filename()
        assert isinstance(fname, str)
        assert len(fname) > 0

    def test_contains_screen_name(self):
        assert 'screen' in screen_filename()


class TestScreenClientProperties:
    def test_array_shape(self, client):
        arr = client.array
        assert arr.shape == (8, 8)
        assert arr.dtype == np.uint16

    def test_rgb_array_shape(self, client):
        arr = client.rgb_array
        assert arr.shape == (8, 8, 3)
        assert arr.dtype == np.uint8

    def test_timestamp_is_float(self, client):
        ts = client.timestamp
        assert isinstance(ts, float)
        assert ts > 0

    def test_initial_pixels_all_zero(self, client):
        arr = client.array
        assert arr.sum() == 0


class TestScreenClientWrite:
    def test_written_pixel_visible_in_array(self, tmp_screen_file, client):
        # Write a red pixel (RGB565: r=31, g=0, b=0 → 0xF800)
        red565 = struct.pack('<H', 0xF800)
        with open(tmp_screen_file, 'r+b') as f:
            f.seek(0)
            f.write(red565)
        # Force mmap refresh by re-reading
        arr = client.array
        assert arr[0, 0] == 0xF800

    def test_rgb_array_nonzero_after_write(self, tmp_screen_file, client):
        # Write a bright green pixel at (0,0): RGB565 0x07E0
        green565 = struct.pack('<H', 0x07E0)
        with open(tmp_screen_file, 'r+b') as f:
            f.seek(0)
            f.write(green565)
        rgb = client.rgb_array
        # Green channel should be non-zero
        assert rgb[0, 0, 1] > 0


class TestScreenClientGamma:
    def test_gamma_default_constants(self):
        assert len(GAMMA_DEFAULT) == 32
        assert GAMMA_DEFAULT[0] == 0
        assert GAMMA_DEFAULT[-1] == 31

    def test_gamma_low_constants(self):
        assert len(GAMMA_LOW) == 32

    def test_gamma_rgbled_lookup_exists(self, client):
        assert client._gamma_rgbled.shape == (32,)


class TestScreenClientClose:
    def test_close_stops_touch_thread(self, tmp_screen_file):
        c = ScreenClient()
        c.close()
        assert c._fd is None
        assert c._map is None

    def test_close_idempotent(self, tmp_screen_file):
        c = ScreenClient()
        c.close()
        # should not raise
        c.close()


from unittest.mock import patch, MagicMock
from sense_emu.screen import screen_filename, init_screen, ScreenClient


class TestScreenFilenameExtended:
    def test_no_shm_uses_tmp(self):
        with patch('os.path.exists', return_value=False):
            result = screen_filename()
        assert result == '/tmp/rpi-sense-emu-screen'

    def test_windows_path(self):
        with patch('sys.platform', 'win32'), \
             patch.dict('os.environ', {'TEMP': '/tmp/wintemp'}):
            result = screen_filename()
        assert 'rpi-sense-emu-screen' in result


class TestInitScreen:
    def test_creates_file_when_missing(self, tmp_path):
        path = str(tmp_path / 'new_screen')
        with patch('sense_emu.screen.screen_filename', return_value=path):
            fd = init_screen()
        assert os.path.exists(path)
        assert fd.seek(0, 2) >= 160  # at least 160 bytes
        fd.close()


class TestTouchRunFallback:
    def test_touch_run_without_fd_support(self, tmp_screen_file):
        """Cover the NotImplementedError fallback path in _touch_run."""
        c = ScreenClient()
        # Stop the background thread
        c._touch_stop.set()
        c._touch_thread.join()
        c._touch_thread = None

        # Patch supports_fd to be empty so os.utime not in os.supports_fd
        c._touch_stop.clear()
        c._touch_stop.set()  # set immediately so while loop exits
        with patch('os.supports_fd', new=frozenset()):
            c._touch_run()

        # Properly close: clear numpy refs first to avoid BufferError
        c._screen = None
        c._gamma = None
        c._map.close()
        c._fd.close()
        c._fd = None
        c._map = None

    def test_touch_run_loop_executes(self, tmp_screen_file):
        """Cover the while loop body in _touch_run."""
        c = ScreenClient()
        c._touch_stop.set()
        c._touch_thread.join()
        c._touch_thread = None

        # Mock _touch_stop.wait to return False once (enter loop) then True (exit)
        responses = iter([False, True])
        orig_wait = c._touch_stop.wait

        def mock_wait(timeout=None):
            try:
                return next(responses)
            except StopIteration:
                return True

        c._touch_stop.wait = mock_wait
        c._touch_run()  # should execute loop body once (line 126)

        # Restore for proper cleanup
        c._touch_stop.wait = orig_wait
        c._touch_stop.set()
        # Properly close: clear numpy refs first to avoid BufferError
        c._screen = None
        c._gamma = None
        c._map.close()
        c._fd.close()
        c._fd = None
        c._map = None
