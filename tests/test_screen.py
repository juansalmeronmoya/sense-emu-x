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
