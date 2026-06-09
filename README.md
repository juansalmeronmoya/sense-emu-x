# Sense HAT Emulator for Windows/Linux/macOS

⚠️UNDER DEVELOPMENT⚠️
A functional emulator of the **Sense HAT for Raspberry Pi** that works on Windows, Linux, and macOS. Simulates all sensors (temperature, pressure, humidity, gyroscope, accelerometer) with an interactive graphical interface.

![Sense HAT Emulator](sense_emu/sense_emu_gui.png)

## ✨ Features

- ✅ **8×8 LED Matrix** with real-time visualization
- ✅ **Complete sensors**: Temperature, pressure, humidity, orientation
- ✅ **Virtual joystick** with 5 directions
- ✅ **Interactive GUI** with sliders
- ✅ **Compatible with Windows, Linux, and macOS**
- ✅ **Python library** for use in your scripts
- ✅ **100% compatible** with original Sense HAT code

## 🚀 Quick Installation

### 1️⃣ Clone or download the repository

```bash
git clone <repo-url>
cd sense-emu-x
```

### 2️⃣ Create a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

### 3️⃣ Install the module

```bash
pip install -e ".[gui]"
```

✅ **Done!** You're ready to use the emulator.

## 💻 Usage

### Option A: Graphical Interface (Recommended)

```bash
sense_emu_gui
```

Or:

```bash
python -m sense_emu.pyside_main
```

**In the GUI you can:**
- 🎨 View the LED matrix with real-time colors
- 🎮 Press joystick buttons
- 🎚️ Adjust sensors with sliders
- 📏 Resize the window (LED matrix always stays square)

### Option B: Program with Python

```python
from sense_emu import SenseHat
import time

hat = SenseHat()

# Read sensors
print(f"Temperature: {hat.temperature}°C")
print(f"Humidity: {hat.humidity}%")

# Control LED
hat.set_pixel(0, 0, (255, 0, 0))  # Red pixel at (0,0)
hat.clear()  # Clear screen

# Joystick
hat.stick.direction_up = lambda: print("Up pressed!")

time.sleep(2)
hat.clear()
```

## 📚 Complete Documentation

For detailed instructions on:
- **Advanced installation**
- **Complete module API**
- **Development and contribution**
- **Testing and coverage**
- **Troubleshooting**

👉 See **[DEVELOPMENT.md](DEVELOPMENT.md)**

## 🏗️ Project Structure

```
sense-emu-x/
├── sense_emu/           # Main module
│   ├── sense_hat.py     # SenseHat class
│   ├── screen.py        # LED matrix
│   ├── pyside_app.py    # GUI
│   └── ...
├── tests/               # Unit tests (427 tests ✅)
├── README.md            # This file
├── DEVELOPMENT.md       # Development guide
└── setup.cfg            # Configuration
```

## 🧪 Tests

All tests pass with **91%+ coverage**:

```bash
pytest                          # Run all tests
pytest tests/test_sense_hat.py  # Specific test
pytest --cov=sense_emu          # With coverage report
```

**Results:**
- ✅ 427 tests passing
- ✅ 1 test skipped (Unix-specific on Windows)
- ✅ 91.67% code coverage

## 🆘 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: No module named 'sense_emu'` | Make sure you activated the venv and ran `pip install -e .` |
| "Port already in use" | Wait 30 seconds or restart the application |
| LED matrix black | Verify that `/tmp/rpi-sense-emu-screen` file exists |
| GUI not responding | Open a new terminal and run `sense_emu_gui` |

👉 See [DEVELOPMENT.md](DEVELOPMENT.md) for more troubleshooting.

## 📦 Dependencies

- **Python 3.8+**
- **numpy** - Numerical processing
- **Pillow** - Image processing
- **PySide6** - GUI (included with `[gui]` installation)

Optional:
- **pytest** - Testing (`pip install -e ".[test]"`)
- **sphinx** - Docs (`pip install -e ".[doc]"`)
- **textual** - TUI (`pip install -e ".[tui]"`)

## 📄 License

- **Library** (`sense_emu/`): LGPL 2.1+
- **GUI and tools**: GPL 2.0+

## 🔗 Useful Links

- 📖 [Official documentation](https://sense-emu.readthedocs.io)
- 🐛 [Bug reports](https://github.com/RPi-Distro/python-sense-emu/issues)
- 📦 [PyPI](https://pypi.org/project/sense-emu/)
- 🏠 [Sense HAT hardware](https://www.raspberrypi.org/products/sense-hat/)

## 🤝 Contributing

Contributions are welcome! See [DEVELOPMENT.md](DEVELOPMENT.md) for:
- How to set up your development environment
- Code standards
- How to run tests
- Checklist before committing

## 💡 Quick Examples

### Display colors on the matrix

```python
from sense_emu import SenseHat

hat = SenseHat()

# Red to blue gradient
for i in range(8):
    hat.set_pixel(i, 0, (255 * i // 8, 0, 255 * (8-i) // 8))

# Show all red
hat.clear((255, 0, 0))
```

### Record sensors to file

```bash
sense_rec data.bin --duration 60
sense_play data.bin            # Playback
sense_csv data.bin -o out.csv  # Export to CSV
```

### Use with threading

```python
from sense_emu import SenseHat
import threading
import time

hat = SenseHat()

def read_sensors():
    while True:
        print(f"T={hat.temperature:.1f}°C H={hat.humidity:.0f}%")
        time.sleep(1)

thread = threading.Thread(target=read_sensors, daemon=True)
thread.start()

# Your code here
time.sleep(10)
hat.clear()
```

---

**First time?** → Start with [DEVELOPMENT.md](DEVELOPMENT.md)

**Need help?** → See the [Troubleshooting](#-quick-troubleshooting) section

**Last updated:** 2026-06-07 | **Version:** 1.0.0 (Windows-compatible)
