"""
Tests for SenseHat LED matrix and sensor API.

We mock out:
- EmulatorLock.wait → True (emulator already running)
- screen_filename → tmp file (so _get_fb_device returns it)
- RTIMU module → fake with configurable returns
- SenseStick.__init__ → no-op (avoids socket connections)
"""
import os
import sys
import struct
import socket as _socket
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from sense_emu.lock import _LOCK_MAGIC

# Platform-appropriate socket family for stick tests
if sys.platform.startswith('win'):
    _STICK_FAMILY = _socket.AF_INET
else:
    _STICK_FAMILY = _socket.AF_UNIX


# ---------------------------------------------------------------------------
# Build a minimal RTIMU mock
# ---------------------------------------------------------------------------

def _make_rtimu_mock():
    mock_settings = MagicMock()
    mock_imu = MagicMock()
    mock_imu.IMUInit.return_value = True
    mock_imu.IMURead.return_value = True
    mock_imu.IMUGetPollInterval.return_value = 3  # ms
    mock_imu.getAccel.return_value = (0.0, 0.0, 1.0)
    mock_imu.getGyro.return_value = (0.0, 0.0, 0.0)
    mock_imu.getCompass.return_value = (0.33, 0.0, 0.0)
    mock_imu.getFusionData.return_value = (0.0, 0.0, 0.0)
    mock_imu.getIMUData.return_value = {
        'accelValid': True,
        'accel': (0.0, 0.0, 1.0),
        'gyroValid': True,
        'gyro': (0.0, 0.0, 0.0),
        'compassValid': True,
        'compass': (0.33, 0.0, 0.0),
        'fusionPoseValid': True,
        'fusionPose': (0.0, 0.0, 0.0),
    }

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
def hat(tmp_screen_file, tmp_lock_file, tmp_stick_addr):
    rtimu_mock = _make_rtimu_mock()

    # Write a held lock (our PID) so EmulatorLock.wait returns True
    with open(tmp_lock_file, 'w') as f:
        f.write('%d\n%s\n' % (os.getpid(), _LOCK_MAGIC))

    with patch.dict('sys.modules', {'RTIMU': rtimu_mock}), \
         patch('sense_emu.sense_hat.RTIMU', rtimu_mock), \
         patch('sense_emu.lock.lock_filename', return_value=tmp_lock_file), \
         patch('sense_emu.stick.stick_address',
               return_value=(_STICK_FAMILY, _socket.SOCK_DGRAM, tmp_stick_addr)):
        from sense_emu import sense_hat as sh_mod
        # Reload to pick up patches
        import importlib
        importlib.reload(sh_mod)
        hat = sh_mod.SenseHat.__new__(sh_mod.SenseHat)
        hat._fb_device = tmp_screen_file
        hat._rotation = 0
        import numpy as _np
        pix_map0 = _np.array([
            [ 0,  1,  2,  3,  4,  5,  6,  7],
            [ 8,  9, 10, 11, 12, 13, 14, 15],
            [16, 17, 18, 19, 20, 21, 22, 23],
            [24, 25, 26, 27, 28, 29, 30, 31],
            [32, 33, 34, 35, 36, 37, 38, 39],
            [40, 41, 42, 43, 44, 45, 46, 47],
            [48, 49, 50, 51, 52, 53, 54, 55],
            [56, 57, 58, 59, 60, 61, 62, 63],
        ], int)
        hat._pix_map = {
              0: pix_map0,
             90: _np.rot90(pix_map0),
            180: _np.rot90(_np.rot90(pix_map0)),
            270: _np.rot90(_np.rot90(_np.rot90(pix_map0))),
        }
        hat._imu = rtimu_mock.RTIMU.return_value
        hat._imu_settings = rtimu_mock.Settings.return_value
        hat._imu_init = False
        hat._imu_poll_interval = 0.001  # 1ms — set for tests that skip _init_imu
        hat._pressure = rtimu_mock.RTPressure.return_value
        hat._pressure_init = False
        hat._humidity = rtimu_mock.RTHumidity.return_value
        hat._humidity_init = False
        hat._last_orientation = {'pitch': 0, 'roll': 0, 'yaw': 0}
        raw = {'x': 0, 'y': 0, 'z': 0}
        from copy import deepcopy
        hat._last_compass_raw = deepcopy(raw)
        hat._last_gyro_raw = deepcopy(raw)
        hat._last_accel_raw = deepcopy(raw)
        hat._compass_enabled = False
        hat._gyro_enabled = False
        hat._accel_enabled = False
        hat._stick = MagicMock()
        # Load text assets
        dir_path = os.path.dirname(sh_mod.__file__)
        hat._load_text_assets(
            os.path.join(dir_path, 'sense_hat_text.png'),
            os.path.join(dir_path, 'sense_hat_text.txt'),
        )
        yield hat


class TestPackUnpack:
    def test_pack_bin_roundtrip(self, hat):
        for r, g, b in [(255, 0, 0), (0, 255, 0), (0, 0, 255), (128, 128, 128)]:
            packed = hat._pack_bin([r, g, b])
            unpacked = hat._unpack_bin(packed)
            # RGB565 has lower bit depth, allow rounding
            assert abs(unpacked[0] - (r & ~0x7)) <= 8
            assert abs(unpacked[1] - (g & ~0x3)) <= 4
            assert abs(unpacked[2] - (b & ~0x7)) <= 8

    def test_pack_black(self, hat):
        packed = hat._pack_bin([0, 0, 0])
        assert struct.unpack('H', packed)[0] == 0

    def test_unpack_zero_is_black(self, hat):
        assert hat._unpack_bin(b'\x00\x00') == [0, 0, 0]


class TestPixelOperations:
    def test_set_and_get_pixel(self, hat):
        hat.set_pixel(0, 0, 248, 0, 0)  # bright red, rounds to RGB565
        pix = hat.get_pixel(0, 0)
        assert pix[0] > 200  # red channel dominant
        assert pix[1] < 10
        assert pix[2] < 10

    def test_set_pixel_tuple_form(self, hat):
        hat.set_pixel(3, 4, (0, 248, 0))
        pix = hat.get_pixel(3, 4)
        assert pix[1] > 200

    def test_set_pixel_x_out_of_range(self, hat):
        with pytest.raises(ValueError):
            hat.set_pixel(8, 0, 0, 0, 0)

    def test_set_pixel_y_out_of_range(self, hat):
        with pytest.raises(ValueError):
            hat.set_pixel(0, 8, 0, 0, 0)

    def test_set_pixel_invalid_color(self, hat):
        with pytest.raises(ValueError):
            hat.set_pixel(0, 0, 300, 0, 0)

    def test_get_pixel_x_out_of_range(self, hat):
        with pytest.raises(ValueError):
            hat.get_pixel(8, 0)

    def test_set_pixels_64_pixels(self, hat):
        pixels = [[i, i, i] for i in range(64)]
        hat.set_pixels(pixels)
        result = hat.get_pixels()
        assert len(result) == 64

    def test_set_pixels_wrong_count_raises(self, hat):
        with pytest.raises(ValueError):
            hat.set_pixels([[0, 0, 0]] * 63)

    def test_set_pixels_invalid_pixel_raises(self, hat):
        pixels = [[0, 0, 0]] * 64
        pixels[5] = [0, 0]
        with pytest.raises(ValueError):
            hat.set_pixels(pixels)

    def test_clear_all_black(self, hat):
        hat.set_pixel(0, 0, 255, 255, 255)
        hat.clear()
        for pix in hat.get_pixels():
            assert pix == [0, 0, 0]

    def test_clear_with_color(self, hat):
        hat.clear(0, 0, 248)
        pix = hat.get_pixel(0, 0)
        assert pix[2] > 200


class TestFlipAndRotate:
    def test_flip_h_reverses_rows(self, hat):
        # Use multiples of 8 to survive RGB565 red-channel encoding (5 bits → >>3)
        pixels = [[(col * 8) % 256, 0, 0] for row in range(8) for col in range(8)]
        hat.set_pixels(pixels)
        flipped = hat.flip_h(redraw=False)
        # flip_h reverses each row; compare using the frame-buffer read-back
        # (after the RGB565 round-trip) from get_pixels()
        fb_pixels = hat.get_pixels()
        refl = []
        for row in range(8):
            refl.extend(reversed(fb_pixels[row * 8: row * 8 + 8]))
        for i in range(64):
            assert flipped[i] == refl[i]

    def test_flip_v_reverses_columns(self, hat):
        hat.clear()
        # Set row 0 to red, row 7 to blue (survives RGB565)
        hat.set_pixel(0, 0, 248, 0, 0)
        hat.set_pixel(0, 7, 0, 0, 248)
        flipped = hat.flip_v(redraw=False)
        # After vertical flip: what was row 7 (bottom) becomes row 0 (top)
        # flipped[0] corresponds to original row 7, pixel 0
        assert flipped[0][2] > 100  # blue dominant (from original row 7)

    def test_set_rotation_valid(self, hat):
        for r in (0, 90, 180, 270):
            hat.set_rotation(r, redraw=False)
            assert hat._rotation == r

    def test_set_rotation_invalid_raises(self, hat):
        with pytest.raises(ValueError):
            hat.set_rotation(45)

    def test_rotation_property_setter(self, hat):
        hat.rotation = 90
        assert hat._rotation == 90


class TestTextAssets:
    def test_text_dict_loaded(self, hat):
        assert len(hat._text_dict) > 0

    def test_space_character_present(self, hat):
        assert ' ' in hat._text_dict

    def test_get_char_pixels_returns_list(self, hat):
        pix = hat._get_char_pixels('A')
        assert isinstance(pix, list)
        assert len(pix) > 0

    def test_get_char_pixels_unknown_returns_question_mark(self, hat):
        pix_q = hat._get_char_pixels('?')
        pix_unknown = hat._get_char_pixels('\x00')
        assert pix_q == pix_unknown


class TestGamma:
    def test_gamma_property_returns_tuple(self, hat):
        g = hat.gamma
        assert len(g) == 32

    def test_gamma_setter(self, hat):
        new_gamma = list(range(32))
        hat.gamma = new_gamma
        g = hat.gamma
        assert list(g) == new_gamma

    def test_low_light_setter(self, hat):
        hat.low_light = True
        g = hat.gamma
        from sense_emu.screen import GAMMA_LOW
        assert list(g) == GAMMA_LOW

    def test_low_light_false_restores_default(self, hat):
        hat.low_light = True
        hat.low_light = False
        g = hat.gamma
        from sense_emu.screen import GAMMA_DEFAULT
        assert list(g) == GAMMA_DEFAULT

    def test_gamma_reset(self, hat):
        hat.gamma = list(range(32))
        hat.gamma_reset()
        from sense_emu.screen import GAMMA_DEFAULT
        assert list(hat.gamma) == GAMMA_DEFAULT


class TestSensors:
    def test_get_humidity(self, hat):
        result = hat.get_humidity()
        assert isinstance(result, float)
        assert result == pytest.approx(45.0)

    def test_humidity_property(self, hat):
        assert isinstance(hat.humidity, float)

    def test_get_pressure(self, hat):
        result = hat.get_pressure()
        assert isinstance(result, float)
        assert result == pytest.approx(1013.0)

    def test_pressure_property(self, hat):
        assert isinstance(hat.pressure, float)

    def test_get_temperature_from_humidity(self, hat):
        result = hat.get_temperature_from_humidity()
        assert isinstance(result, float)

    def test_get_temperature_from_pressure(self, hat):
        result = hat.get_temperature_from_pressure()
        assert isinstance(result, float)

    def test_get_temperature(self, hat):
        result = hat.get_temperature()
        assert isinstance(result, float)

    def test_temperature_property(self, hat):
        assert isinstance(hat.temperature, float)

    def test_get_orientation_degrees(self, hat):
        hat._imu.getAccel.return_value = (0.0, 0.0, 1.0)
        hat._imu.getGyro.return_value = (0.0, 0.0, 0.0)
        hat._imu.getCompass.return_value = (0.33, 0.0, 0.0)
        hat._imu.getFusionData.return_value = (10.0, 20.0, 30.0)
        result = hat.get_orientation()
        assert 'pitch' in result
        assert 'roll' in result
        assert 'yaw' in result

    def test_set_imu_config(self, hat):
        hat.set_imu_config(True, True, True)
        assert hat._compass_enabled is True
        assert hat._gyro_enabled is True
        assert hat._accel_enabled is True

    def test_stick_property(self, hat):
        stick = hat.stick
        assert stick is not None

    def test_get_compass(self, hat):
        hat._imu.getFusionData.return_value = (0.0, 0.0, 45.0)
        result = hat.get_compass()
        assert isinstance(result, float)

    def test_get_accelerometer_raw(self, hat):
        hat._imu.getIMUData.return_value = {
            'accelValid': True, 'accel': (0.1, 0.2, 9.8),
            'gyroValid': False, 'gyro': (0, 0, 0),
            'compassValid': False, 'compass': (0, 0, 0),
            'fusionPoseValid': False, 'fusionPose': (0, 0, 0),
        }
        result = hat.get_accelerometer_raw()
        assert result is not None
        assert 'x' in result

    def test_get_gyroscope_raw(self, hat):
        hat._imu.getIMUData.return_value = {
            'accelValid': False, 'accel': (0, 0, 0),
            'gyroValid': True, 'gyro': (0.0, 0.1, 0.0),
            'compassValid': False, 'compass': (0, 0, 0),
            'fusionPoseValid': False, 'fusionPose': (0, 0, 0),
        }
        result = hat.get_gyroscope_raw()
        assert result is not None
        assert 'x' in result

    def test_rotation_getter(self, hat):
        hat._rotation = 90
        assert hat.rotation == 90

    def test_flip_h_with_redraw(self, hat):
        hat.clear()
        result = hat.flip_h(redraw=True)
        assert len(result) == 64

    def test_flip_v_with_redraw(self, hat):
        hat.clear()
        result = hat.flip_v(redraw=True)
        assert len(result) == 64

    def test_set_pixel_invalid_pixel_length(self, hat):
        with pytest.raises(ValueError):
            hat.set_pixel(0, 0, [0, 0])

    def test_set_pixel_wrong_arg_count(self, hat):
        with pytest.raises(ValueError):
            hat.set_pixel(0, 0, 10, 20)

    def test_get_pixel_y_out_of_range(self, hat):
        with pytest.raises(ValueError):
            hat.get_pixel(0, 8)

    def test_clear_with_single_tuple(self, hat):
        hat.clear((0, 0, 248))
        pix = hat.get_pixel(0, 0)
        assert pix[2] > 200

    def test_clear_wrong_args_raises(self, hat):
        with pytest.raises(ValueError):
            hat.clear(0, 0)

    def test_show_letter(self, hat):
        with patch('sense_emu.sense_hat.time') as mock_time:
            mock_time.sleep = lambda _: None
            hat.show_letter('A')

    def test_show_letter_too_long_raises(self, hat):
        with pytest.raises(ValueError):
            hat.show_letter('AB')

    def test_show_message(self, hat):
        with patch('sense_emu.sense_hat.time') as mock_time:
            mock_time.sleep = lambda _: None
            hat.show_message('Hi', scroll_speed=0)

    def test_gamma_wrong_length_raises(self, hat):
        with pytest.raises(ValueError):
            hat.gamma = [0] * 16

    def test_gamma_out_of_range_raises(self, hat):
        with pytest.raises(ValueError):
            hat.gamma = [32] * 32

    def test_low_light_getter(self, hat):
        hat.low_light = True
        assert hat.low_light is True
        hat.low_light = False
        assert hat.low_light is False

    def test_humidity_init_failure_raises(self, hat):
        hat._humidity.humidityInit.return_value = False
        hat._humidity_init = False
        with pytest.raises(OSError):
            hat._init_humidity()

    def test_pressure_init_failure_raises(self, hat):
        hat._pressure.pressureInit.return_value = False
        hat._pressure_init = False
        with pytest.raises(OSError):
            hat._init_pressure()

    def test_get_humidity_when_invalid(self, hat):
        hat._humidity.humidityRead.return_value = (False, 0.0, False, 0.0)
        result = hat.get_humidity()
        assert result == 0

    def test_get_temperature_from_humidity_when_invalid(self, hat):
        hat._humidity.humidityRead.return_value = (False, 0.0, False, 0.0)
        result = hat.get_temperature_from_humidity()
        assert result == 0

    def test_get_temperature_from_pressure_when_invalid(self, hat):
        hat._pressure.pressureRead.return_value = (False, 0.0, False, 0.0)
        result = hat.get_temperature_from_pressure()
        assert result == 0

    def test_get_pressure_when_invalid(self, hat):
        hat._pressure.pressureRead.return_value = (False, 0.0, False, 0.0)
        result = hat.get_pressure()
        assert result == 0

    def test_temp_property(self, hat):
        assert isinstance(hat.temp, float)

    def test_temperature_property(self, hat):
        assert isinstance(hat.temperature, float)

    def test_get_gyroscope(self, hat):
        result = hat.get_gyroscope()
        assert 'pitch' in result

    def test_gyro_property(self, hat):
        result = hat.gyro
        assert isinstance(result, dict)

    def test_gyroscope_property(self, hat):
        result = hat.gyroscope
        assert isinstance(result, dict)

    def test_get_gyroscope_raw_when_invalid(self, hat):
        hat._imu.getIMUData.return_value = {
            'accelValid': False, 'accel': (0, 0, 0),
            'gyroValid': False, 'gyro': (0, 0, 0),
            'compassValid': False, 'compass': (0, 0, 0),
            'fusionPoseValid': False, 'fusionPose': (0, 0, 0),
        }
        result = hat.get_gyroscope_raw()
        assert 'x' in result

    def test_gyro_raw_property(self, hat):
        result = hat.gyro_raw
        assert isinstance(result, dict)

    def test_gyroscope_raw_property(self, hat):
        result = hat.gyroscope_raw
        assert isinstance(result, dict)

    def test_get_accelerometer(self, hat):
        result = hat.get_accelerometer()
        assert 'pitch' in result

    def test_accel_property(self, hat):
        result = hat.accel
        assert isinstance(result, dict)

    def test_accelerometer_property(self, hat):
        result = hat.accelerometer
        assert isinstance(result, dict)

    def test_get_accelerometer_raw_when_invalid(self, hat):
        hat._imu.getIMUData.return_value = {
            'accelValid': False, 'accel': (0, 0, 0),
            'gyroValid': False, 'gyro': (0, 0, 0),
            'compassValid': False, 'compass': (0, 0, 0),
            'fusionPoseValid': False, 'fusionPose': (0, 0, 0),
        }
        result = hat.get_accelerometer_raw()
        assert 'x' in result

    def test_accel_raw_property(self, hat):
        result = hat.accel_raw
        assert isinstance(result, dict)

    def test_accelerometer_raw_property(self, hat):
        result = hat.accelerometer_raw
        assert isinstance(result, dict)

    def test_orientation_radians_property(self, hat):
        result = hat.orientation_radians
        assert isinstance(result, dict)

    def test_orientation_property(self, hat):
        result = hat.orientation
        assert isinstance(result, dict)

    def test_get_orientation_radians(self, hat):
        hat._imu.getIMUData.return_value = {
            'accelValid': False, 'accel': (0, 0, 0),
            'gyroValid': False, 'gyro': (0, 0, 0),
            'compassValid': False, 'compass': (0, 0, 0),
            'fusionPoseValid': True, 'fusionPose': (0.1, 0.2, 0.3),
        }
        result = hat.get_orientation_radians()
        assert 'pitch' in result
        assert 'roll' in result
        assert 'yaw' in result

    def test_get_compass_raw(self, hat):
        hat._imu.getIMUData.return_value = {
            'accelValid': False, 'accel': (0, 0, 0),
            'gyroValid': False, 'gyro': (0, 0, 0),
            'compassValid': True, 'compass': (0.33, 0.0, 0.0),
            'fusionPoseValid': False, 'fusionPose': (0, 0, 0),
        }
        result = hat.get_compass_raw()
        assert 'x' in result

    def test_compass_raw_property(self, hat):
        result = hat.compass_raw
        assert isinstance(result, dict)

    def test_set_imu_config_type_error(self, hat):
        with pytest.raises(TypeError):
            hat.set_imu_config('yes', True, True)

    def test_imu_init_failure_raises_oserror(self, hat):
        hat._imu.IMUInit.return_value = False
        hat._imu_init = False
        with pytest.raises(OSError):
            hat._init_imu()

    def test_load_image_file_not_found(self, hat, tmp_path):
        with pytest.raises(IOError):
            hat.load_image(str(tmp_path / 'nonexistent.png'))

    def test_load_image_with_redraw(self, hat, tmp_path):
        from PIL import Image
        img = Image.new('RGB', (8, 8), color=(255, 0, 0))
        path = str(tmp_path / 'test.png')
        img.save(path)
        result = hat.load_image(path, redraw=True)
        assert len(result) == 64

    def test_load_image_without_redraw(self, hat, tmp_path):
        from PIL import Image
        img = Image.new('RGB', (8, 8), color=(0, 255, 0))
        path = str(tmp_path / 'test.png')
        img.save(path)
        result = hat.load_image(path, redraw=False)
        assert len(result) == 64

    def test_get_raw_data_when_read_imu_fails(self, hat):
        hat._imu.IMURead.return_value = False
        hat._imu_init = True
        result = hat._get_raw_data('accelValid', 'accel')
        assert result is None


class TestSenseHatInit:
    def test_full_init(self, tmp_screen_file, tmp_lock_file, tmp_stick_addr):
        """Cover __init__ body (lines 78-145)."""
        rtimu_mock = _make_rtimu_mock()
        # Write our PID to the lock file so lock.wait() returns True
        with open(tmp_lock_file, 'w') as f:
            f.write('%d\n' % os.getpid())
        # Patch SenseStick to avoid real socket connection
        import sense_emu.sense_hat as sh_mod
        import importlib
        with patch.dict('sys.modules', {'RTIMU': rtimu_mock}), \
             patch('sense_emu.sense_hat.RTIMU', rtimu_mock), \
             patch('sense_emu.lock.lock_filename', return_value=tmp_lock_file), \
             patch('sense_emu.stick.stick_address',
                   return_value=(_STICK_FAMILY, _socket.SOCK_DGRAM, tmp_stick_addr)):
            importlib.reload(sh_mod)
            # Create a real StickServer so SenseStick can connect
            from sense_emu.stick import StickServer
            server = StickServer()
            try:
                hat = sh_mod.SenseHat()
                assert hat._rotation == 0
                assert hat._fb_device == tmp_screen_file
                hat._stick.close()
            finally:
                server.close()

    def test_init_when_lock_not_held_spawns_gui(self, tmp_screen_file, tmp_lock_file, tmp_stick_addr):
        """Cover lines 79-91: when lock.wait() returns False, spawns GUI."""
        rtimu_mock = _make_rtimu_mock()
        # Don't write lock file, so lock.wait() returns False
        import sense_emu.sense_hat as sh_mod
        import importlib
        with patch.dict('sys.modules', {'RTIMU': rtimu_mock}), \
             patch('sense_emu.sense_hat.RTIMU', rtimu_mock), \
             patch('sense_emu.lock.lock_filename', return_value=tmp_lock_file), \
             patch('sense_emu.stick.stick_address',
                   return_value=(_STICK_FAMILY, _socket.SOCK_DGRAM, tmp_stick_addr)), \
             patch('sense_emu.sense_hat.sp.Popen') as mock_popen:
            importlib.reload(sh_mod)
            from sense_emu.stick import StickServer
            server = StickServer()
            try:
                hat = sh_mod.SenseHat()
                assert hat._rotation == 0
                # Popen was called to spawn GUI
                mock_popen.assert_called_once()
                hat._stick.close()
            finally:
                server.close()

    def test_init_no_fb_device_raises(self, tmp_lock_file, tmp_stick_addr):
        """Cover line 95: OSError when fb_device is None."""
        rtimu_mock = _make_rtimu_mock()
        with open(tmp_lock_file, 'w') as f:
            f.write('%d\n' % os.getpid())
        import sense_emu.sense_hat as sh_mod
        import importlib
        with patch.dict('sys.modules', {'RTIMU': rtimu_mock}), \
             patch('sense_emu.sense_hat.RTIMU', rtimu_mock), \
             patch('sense_emu.lock.lock_filename', return_value=tmp_lock_file), \
             patch('sense_emu.stick.stick_address',
                   return_value=(_STICK_FAMILY, _socket.SOCK_DGRAM, tmp_stick_addr)):
            importlib.reload(sh_mod)
            with patch.object(sh_mod.SenseHat, '_get_fb_device', return_value=None):
                with pytest.raises(OSError, match='Cannot detect'):
                    hat = sh_mod.SenseHat()


class TestAdditionalSensorBranches:
    def test_init_humidity_already_initialized(self, hat):
        hat._humidity_init = True
        hat._init_humidity()
        hat._humidity.humidityInit.assert_not_called()

    def test_init_pressure_already_initialized(self, hat):
        hat._pressure_init = True
        hat._init_pressure()
        hat._humidity.humidityInit.assert_not_called()

    def test_get_orientation_radians_when_raw_none(self, hat):
        hat._imu.IMURead.return_value = False
        hat._imu_init = True
        result = hat.get_orientation_radians()
        assert isinstance(result, dict)

    def test_gamma_setter_with_array_type(self, hat):
        import array
        buf = array.array('B', range(32))
        hat.gamma = buf

    def test_show_message_no_rotation_adjust(self, hat):
        hat._rotation = 90  # 90-90=0, not < 0, so no adjustment
        with patch('sense_emu.sense_hat.time') as mock_time:
            mock_time.sleep = lambda _: None
            hat.show_message('Hi', scroll_speed=0)
        assert hat._rotation == 90

    def test_show_letter_no_rotation_adjust(self, hat):
        hat._rotation = 90
        with patch('sense_emu.sense_hat.time') as mock_time:
            mock_time.sleep = lambda _: None
            hat.show_letter('A')
        assert hat._rotation == 90

    def test_show_message_with_space_char(self, hat):
        with patch('sense_emu.sense_hat.time') as mock_time:
            mock_time.sleep = lambda _: None
            hat.show_message(' A', scroll_speed=0)

    def test_set_pixels_element_out_of_range(self, hat):
        pixels = [[0, 0, 0]] * 64
        pixels[5] = [300, 0, 0]
        with pytest.raises(ValueError):
            hat.set_pixels(pixels)

    def test_get_fb_device(self, hat, tmp_screen_file):
        result = hat._get_fb_device()
        assert result == tmp_screen_file

    def test_get_settings_file(self, hat):
        rtimu_mock = _make_rtimu_mock()
        import sense_emu.sense_hat as sh_mod
        with patch.dict('sys.modules', {'RTIMU': rtimu_mock}), \
             patch('sense_emu.sense_hat.RTIMU', rtimu_mock):
            result = hat._get_settings_file('RTIMULib')
        assert result is not None
