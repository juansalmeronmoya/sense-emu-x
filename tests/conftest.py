import io
import os
import sys
import mmap
import struct
import time
import socket
import pytest
from unittest.mock import patch, MagicMock

from sense_emu.common import HEADER_REC, DATA_REC
from sense_emu.pressure import PRESSURE_DATA
from sense_emu.humidity import HUMIDITY_DATA
from sense_emu.imu import IMU_DATA
from sense_emu.screen import GAMMA_DEFAULT


# ---------------------------------------------------------------------------
# Low-level temp file helpers
# ---------------------------------------------------------------------------

def _make_temp_file(tmp_path, name, size, initial=None):
    path = tmp_path / name
    with open(path, 'wb') as f:
        if initial:
            f.write(initial)
        else:
            f.write(b'\x00' * size)
    return str(path)


# ---------------------------------------------------------------------------
# Fixtures: per-sensor temp files + module-level patches
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_pressure_file(tmp_path):
    path = _make_temp_file(tmp_path, 'pressure', PRESSURE_DATA.size)
    with patch('sense_emu.pressure.pressure_filename', return_value=path):
        yield path


@pytest.fixture
def tmp_humidity_file(tmp_path):
    path = _make_temp_file(tmp_path, 'humidity', HUMIDITY_DATA.size)
    with patch('sense_emu.humidity.humidity_filename', return_value=path):
        yield path


@pytest.fixture
def tmp_imu_file(tmp_path):
    path = _make_temp_file(tmp_path, 'imu', IMU_DATA.size)
    with patch('sense_emu.imu.imu_filename', return_value=path):
        yield path


@pytest.fixture
def tmp_screen_file(tmp_path):
    path = _make_temp_file(
        tmp_path, 'screen', 160,
        b'\x00\x00' * 64 + bytes(GAMMA_DEFAULT),
    )
    with patch('sense_emu.screen.screen_filename', return_value=path):
        yield path


@pytest.fixture
def tmp_lock_file(tmp_path):
    path = str(tmp_path / 'lock')
    with patch('sense_emu.lock.lock_filename', return_value=path):
        yield path


# ---------------------------------------------------------------------------
# Fixture: stick address in a temp dir so we don't collide
# ---------------------------------------------------------------------------

def _make_stick_address(tmp_path):
    if sys.platform.startswith('win'):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        return (socket.AF_INET, socket.SOCK_DGRAM, ('127.0.0.1', port))
    return (socket.AF_UNIX, socket.SOCK_DGRAM, str(tmp_path / 'stick'))


@pytest.fixture
def tmp_stick_addr(tmp_path):
    family, sock_type, addr = _make_stick_address(tmp_path)
    with patch('sense_emu.stick.stick_address',
               return_value=(family, sock_type, addr)):
        yield addr


# ---------------------------------------------------------------------------
# Composite fixture: EmulatorController with all temp files
# ---------------------------------------------------------------------------

@pytest.fixture
def emulator_patches(tmp_path):
    """Apply all temp-file/socket patches for the emulator without constructing
    an EmulatorController. Lets tests build (or fail to build) their own."""
    pressure_path = _make_temp_file(tmp_path, 'pressure', PRESSURE_DATA.size)
    humidity_path = _make_temp_file(tmp_path, 'humidity', HUMIDITY_DATA.size)
    imu_path      = _make_temp_file(tmp_path, 'imu', IMU_DATA.size)
    screen_path   = _make_temp_file(
        tmp_path, 'screen', 160,
        b'\x00\x00' * 64 + bytes(GAMMA_DEFAULT),
    )
    lock_path = str(tmp_path / 'lock')
    stick_family, stick_sock_type, stick_addr = _make_stick_address(tmp_path)
    patches = [
        patch('sense_emu.pressure.pressure_filename', return_value=pressure_path),
        patch('sense_emu.humidity.humidity_filename', return_value=humidity_path),
        patch('sense_emu.imu.imu_filename',           return_value=imu_path),
        patch('sense_emu.screen.screen_filename',     return_value=screen_path),
        patch('sense_emu.lock.lock_filename',         return_value=lock_path),
        patch('sense_emu.stick.stick_address',
              return_value=(stick_family, stick_sock_type, stick_addr)),
    ]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


@pytest.fixture
def emulator(emulator_patches):
    from sense_emu.core import EmulatorController
    ctl = EmulatorController(simulate_imu=False, simulate_env=False)
    yield ctl
    ctl.close()


# ---------------------------------------------------------------------------
# Fixture: a sample binary recording file
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_recording(tmp_path):
    path = tmp_path / 'recording.bin'
    now = time.time()
    with open(path, 'wb') as f:
        f.write(HEADER_REC.pack(b'SENSEHAT', 1, now))
        for i in range(5):
            f.write(DATA_REC.pack(
                now + i * 0.1,
                1013.0 + i, 20.0 + i,   # pressure, ptemp
                45.0 + i,  20.0 + i,    # humidity, htemp
                0.0, 0.0, 1.0,           # accel
                0.0, 0.0, 0.0,           # gyro
                0.33, 0.0, 0.0,          # compass
                0.0, 0.0, 0.0,           # orientation
            ))
    return str(path)
