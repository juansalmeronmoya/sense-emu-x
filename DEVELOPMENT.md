# Sense HAT Emulator - Development Guide

Complete guide to install, use, and develop the Sense HAT emulator for Raspberry Pi.

## 📋 Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Development](#development)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## 🚀 Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git (optional, for cloning the repository)

### Installation from Repository

#### 1. Create a virtual environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate
```

#### 2. Install the module in development mode

```bash
# Install all dependencies (including dev and GUI)
pip install -e ".[gui,test]"
```

Or install specific dependencies:

```bash
# Base module only (no GUI)
pip install -e .

# With PySide6 graphical interface
pip install -e ".[gui]"

# With testing tools
pip install -e ".[test]"

# With everything
pip install -e ".[gui,test,tui,doc]"
```

#### 3. Verify the installation

```bash
# Run tests
pytest

# Verify module imports correctly
python -c "from sense_emu import SenseHat; print('✓ Installation successful')"
```

---

## 💻 Usage

### Programmatic Mode (Python Library)

Use the emulator as a library in your Python scripts:

```python
from sense_emu import SenseHat
import time

# Create an emulator instance
hat = SenseHat()

# Read sensors
temp = hat.temperature
humidity = hat.humidity
pressure = hat.pressure

print(f"Temperature: {temp}°C")
print(f"Humidity: {humidity}%")
print(f"Pressure: {pressure} mbar")

# Control the LED matrix
# Single pixel
hat.set_pixel(0, 0, (255, 0, 0))  # Red in top-left corner

# Full matrix
pixels = [
    (255, 0, 0),      # Red
    (0, 255, 0),      # Green
    (0, 0, 255),      # Blue
    # ... more pixels (64 total for 8x8 matrix)
]
hat.set_pixels(pixels)

# Clear screen
hat.clear()

# Use the joystick
def on_stick_press(event):
    print(f"Joystick: {event.direction} - {event.action}")

hat.stick.direction_up = lambda: print("Up pressed")
hat.stick.direction_down = lambda: print("Down pressed")

# Clean up resources
hat.clear()
```

### Graphical Interface (GUI)

Launch the interactive GUI application:

```bash
# Method 1: Using entry point
sense_emu_gui

# Method 2: Using Python directly
python -m sense_emu.pyside_main
```

**GUI Features:**

- 📊 **8×8 LED Matrix** - Real-time pixel visualization
- 🎮 **Joystick Buttons** - Simulate joystick presses
- 📈 **Sensors**:
  - Orientation (Pitch, Roll, Yaw)
  - Temperature
  - Atmospheric pressure
  - Relative humidity
- 🎚️ **Sliders** - Adjust sensor values in real-time

**Resizing the window:**
- LED matrix always maintains square proportion
- Minimum size: 80×80 pixels
- Maximum size: 800×800 pixels

### Command-line Tools

#### `sense_rec` - Sensor Recorder

Record sensor readings to a file:

```bash
sense_rec output.bin --duration 60
```

#### `sense_play` - Sensor Playback

Playback recorded sensors:

```bash
sense_play output.bin
```

#### `sense_csv` - Export to CSV

Convert recording to CSV:

```bash
sense_csv output.bin -o data.csv --header
```

#### `sense_emu_tui` - Terminal Interface

Interactive terminal interface (experimental):

```bash
sense_emu_tui
```

---

## 🔧 Development

### Project Structure

```
sense-emu-x/
├── sense_emu/              # Main module
│   ├── __init__.py         # Public exports
│   ├── sense_hat.py        # Main SenseHat class
│   ├── screen.py           # LED matrix management
│   ├── imu.py              # Accelerometer/Gyroscope
│   ├── humidity.py         # Humidity sensor
│   ├── pressure.py         # Pressure sensor
│   ├── stick.py            # Joystick control
│   ├── lock.py             # Inter-process locking
│   ├── pyside_app.py       # PySide6 GUI
│   ├── tui.py              # Terminal interface
│   ├── record.py           # Data recording
│   ├── play.py             # Data playback
│   ├── dump.py             # CSV export
│   ├── i18n.py             # Internationalization
│   └── core.py             # Central controller
├── tests/                  # Test suite
│   ├── conftest.py         # Shared fixtures
│   ├── test_*.py           # Tests per module
│   └── ...
├── setup.cfg               # Pytest configuration
├── pyproject.toml          # Build configuration
└── DEVELOPMENT.md          # This file
```

### Execution Flow

1. **User creates `SenseHat()`** → Instantiates the class
2. **`EmulatorController` starts** → Manages all sensors
3. **mmap servers launch** → One for each sensor (pressure, humidity, IMU, screen, joystick)
4. **GUI connects to mmap files** → Reads in real-time
5. **On close**, resources are freed

### Modify the Code

#### Example: Add a new sensor

```python
# 1. Create sense_emu/my_sensor.py
class MySensorServer:
    def __init__(self):
        self.value = 0.0
    
    def set_value(self, val):
        self.value = val

# 2. Integrate in sense_emu/core.py
from .my_sensor import MySensorServer

class EmulatorController:
    def __init__(self):
        self.my_sensor = MySensorServer()

# 3. Export in sense_emu/__init__.py
from .core import EmulatorController

# 4. Create test in tests/test_my_sensor.py
```

#### Example: Modify the GUI

```python
# Edit sense_emu/pyside_app.py
# Layout properties are in the SenseEmuDesktop class

# Add a new slider:
def create_slider_in_group(layout, "My Sensor", 0, 100, 50)
```

### Run in development mode

```bash
# Install in editable mode with all dependencies
pip install -e ".[gui,test,dev]"

# Run tests while developing
pytest --watch

# Or run specific tests
pytest tests/test_sense_hat.py -v

# Run with coverage
pytest --cov=sense_emu --cov-report=html

# Launch GUI for manual testing
python -m sense_emu.pyside_main
```

---

## 🧪 Testing

### Run all tests

```bash
pytest
```

### Specific tests

```bash
# Test a module
pytest tests/test_sense_hat.py -v

# Test a class
pytest tests/test_sense_hat.py::TestSenseHat -v

# Test a specific method
pytest tests/test_sense_hat.py::TestSenseHat::test_init -v

# Tests matching a pattern
pytest -k "screen" -v
```

### Code coverage

```bash
# Generate coverage report
pytest --cov=sense_emu --cov-report=html

# Open coverage/index.html in browser
```

### Coverage Requirements

- Minimum required: **85%**
- Current threshold: **91%** ✅

```bash
# Verify it meets the requirement
pytest --cov=sense_emu --cov-fail-under=85
```

---

## 🐛 Troubleshooting

### Problem: "ModuleNotFoundError: No module named 'sense_emu'"

**Solution:**
```bash
# Make sure venv is activated
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Reinstall the module
pip install -e .
```

### Problem: "OSError: Port already in use"

**Cause:** The joystick port is already being used by another instance.

**Solutions:**
```bash
# Wait a moment (port is freed in ~30 seconds)
# Or kill the previous process
ps aux | grep python  # Linux/Mac
tasklist | grep python  # Windows
```

### Problem: Tests fail with "socket.AF_UNIX not available on Windows"

**Automatic solution:** Already handled in `conftest.py` - uses UDP ports on Windows automatically.

### Problem: LED matrix appears black

**Common causes:**
1. Screen file wasn't created correctly
2. Data isn't written to file
3. RGB565→RGB888 conversion has a bug

**Debug:**
```python
from sense_emu.screen import ScreenClient
client = ScreenClient()
print(client.rgb_array)  # View raw data
```

### Problem: Tests are slow

**Optimize:**
```bash
# Run tests in parallel
pip install pytest-xdist
pytest -n auto

# Run only fast tests
pytest -m "not slow"
```

---

## 📚 Additional Resources

- **Official documentation**: https://sense-emu.readthedocs.io
- **Sense HAT hardware**: https://www.raspberrypi.org/products/sense-hat/
- **GitHub**: https://github.com/RPi-Distro/python-sense-emu
- **Examples**: See `sense_emu/examples/`

---

## 📝 Development Notes

### About mmap Files

The emulator uses memory-mapped files (mmap) to share data between processes:

- **`/tmp/rpi-sense-emu-screen`** (or `%TEMP%` on Windows): 8×8 LED matrix in RGB565
- **`/tmp/rpi-sense-emu-imu`**: Accelerometer/gyroscope data
- **`/tmp/rpi-sense-emu-pressure`**: Pressure/temperature data
- **`/tmp/rpi-sense-emu-humidity`**: Humidity/temperature data
- **`/tmp/rpi-sense-emu-stick`**: Joystick socket (UDP or Unix)

### Data Formats

- **RGB565**: 2 bytes per pixel (R:5 bits, G:6 bits, B:5 bits)
- **Gamma table**: 32 bytes of LUT for brightness correction
- **IMU**: Quaternions in floating point (10-bit precision)

---

## ✅ Contributor Checklist

Before committing:

- [ ] Tests pass: `pytest`
- [ ] Coverage ≥85%: `pytest --cov=sense_emu --cov-fail-under=85`
- [ ] Code formatted (if applicable)
- [ ] Docstrings updated
- [ ] No import warnings

---

## 📄 License

- **Library** (sense_emu/): LGPL 2.1+
- **GUI and tools**: GPL 2.0+

See file headers for specific details.

---

**Last updated:** 2026-06-07
**Python version:** 3.8+
**Supported platforms:** Windows, Linux, macOS
