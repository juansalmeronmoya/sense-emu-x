# Installation Guide - Sense HAT Emulator

Detailed installation instructions for **Windows**, **Linux**, and **macOS**.

## 📋 Prerequisites (All Platforms)

- **Python 3.8 or higher** ([Download](https://www.python.org/downloads/))
- **pip** (included with Python 3.4+)
- Access to a terminal/PowerShell
- ~500 MB of disk space

**Verify you have Python installed:**

```bash
python --version
pip --version
```

If you see versions lower than 3.8, update Python.

---

## 🪟 Windows

### Step 1: Clone/download the repository

**Option A: With Git**

```bash
git clone https://github.com/RPi-Distro/python-sense-emu
cd python-sense-emu
```

**Option B: Without Git**

1. Download the ZIP from GitHub
2. Extract the folder
3. Open PowerShell in that folder

### Step 2: Create virtual environment

```powershell
# Create the virtual environment
python -m venv venv

# Activate the virtual environment
venv\Scripts\activate

# You should see "(venv)" at the start of your command line
```

### Step 3: Install dependencies

```powershell
# Update pip
python -m pip install --upgrade pip

# Install the module with GUI
pip install -e ".[gui]"
```

This step takes **2-3 minutes** the first time.

### Step 4: Verify installation

```powershell
# Option 1: Import the module
python -c "from sense_emu import SenseHat; print('✓ OK')"

# Option 2: Run the GUI
sense_emu_gui
```

If you see "✓ OK" or the GUI opens, you're done!

### Windows Troubleshooting

| Error | Solution |
|-------|----------|
| `python: command not found` | Python is not in PATH. Reinstall with "Add Python to PATH" ✓ |
| `venv\Scripts\activate` doesn't work | Try `python -m venv venv` first |
| `'pip' is not recognized` | Make sure you're in (venv) |
| PySide6 won't install | Run as administrator or use `pip install --user` |

---

## 🐧 Linux (Ubuntu/Debian)

### Step 1: Install system dependencies

```bash
sudo apt-get update
sudo apt-get install python3 python3-pip python3-venv
```

### Step 2: Clone repository

```bash
git clone https://github.com/RPi-Distro/python-sense-emu
cd python-sense-emu
```

### Step 3: Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 4: Install module

```bash
pip install --upgrade pip
pip install -e ".[gui]"
```

### Step 5: Run

```bash
# GUI
sense_emu_gui

# Or from Python
python -m sense_emu.pyside_main
```

### Linux Troubleshooting

| Error | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named '_tkinter'` | `sudo apt-get install python3-tk` |
| PySide6 compilation fails | `sudo apt-get install build-essential python3-dev` |
| Socket permission denied | Use `lsof -i :PORT` to see what uses the port |

---

## 🍎 macOS

### Step 1: Install Homebrew (if not already installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Step 2: Install Python

```bash
brew install python3
```

### Step 3: Clone repository

```bash
git clone https://github.com/RPi-Distro/python-sense-emu
cd python-sense-emu
```

### Step 4: Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 5: Install module

```bash
pip install --upgrade pip
pip install -e ".[gui]"
```

### Step 6: Run

```bash
sense_emu_gui
```

### macOS Troubleshooting

| Error | Solution |
|-------|----------|
| `zsh: command not found: python3` | Install with Homebrew: `brew install python3` |
| PySide6 fails on M1/M2 | Make sure you're using Python ARM64 |
| GUI window doesn't appear | Try: `python -m sense_emu.pyside_main` |

---

## 🔧 Installation with Options

### Library only (without GUI)

```bash
pip install -e .
```

### With testing

```bash
pip install -e ".[test]"
pip install -e ".[gui,test]"  # GUI + Testing
```

### With additional tools

```bash
pip install -e ".[gui,test,doc,tui]"
```

Where:
- `gui` = PySide6 graphical interface
- `test` = pytest and testing tools
- `doc` = Sphinx for documentation
- `tui` = Terminal interface

### Global installation (not recommended)

```bash
# Without creating venv
pip install .

# With GUI
pip install ".[gui]"

# For local user
pip install --user .
```

---

## 📁 Structure after installation

```
your-project/
├── venv/                    # Virtual environment
│   ├── lib/python3.x/
│   │   └── site-packages/   # Installed modules
│   ├── Scripts/ (Windows)
│   └── bin/ (Linux/Mac)
├── sense-emu-x/
│   ├── sense_emu/           # Module
│   ├── tests/               # Tests
│   ├── README.md
│   └── DEVELOPMENT.md
└── my_script.py             # Your Python scripts
```

---

## ✅ Complete Verification

After installation, run this to verify everything:

```bash
# 1. Verify Python
python --version

# 2. Verify pip
pip list | grep sense-emu

# 3. Run tests
pytest

# 4. Test import
python -c "from sense_emu import SenseHat; hat = SenseHat(); print(hat.temperature)"

# 5. Launch GUI
sense_emu_gui
```

If everything works, congratulations! 🎉

---

## 🔄 Update to a newer version

```bash
# Activate venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Update
pip install --upgrade sense-emu
```

---

## 🗑️ Uninstall

```bash
# Option 1: Just deactivate venv (easier)
deactivate  # Deactivate virtual environment
# Then delete the venv/ folder

# Option 2: Complete uninstall
pip uninstall sense-emu
```

---

## 🎓 Next Steps

After installation:

1. **Learn the basics**: Read [README.md](README.md)
2. **Try examples**: See `sense_emu/examples/`
3. **Read the API**: [sense-emu.readthedocs.io](https://sense-emu.readthedocs.io)
4. **Development**: Check [DEVELOPMENT.md](DEVELOPMENT.md)

---

## 🆘 Common Issues

### "pip: command not found"

Python is not in your PATH. Options:
1. Reinstall Python with "Add Python to PATH"
2. Use `python -m pip` instead of `pip`
3. Use the absolute Python: `/usr/bin/python3 -m pip`

### "No module named 'sense_emu'"

You didn't activate the venv. Run:
```bash
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### "Port 53753 already in use"

Another process is using the port. Solutions:
```bash
# Linux/Mac: See what process uses the port
lsof -i :53753
kill -9 <PID>

# Windows: In PowerShell
netstat -ano | findstr :53753
taskkill /PID <PID> /F

# Or just wait 30 seconds and restart
```

### Tests fail

```bash
# Make sure pytest is installed
pip install -e ".[test]"

# Run the tests
pytest -v

# Specific tests
pytest tests/test_sense_hat.py -v
```

---

## 💬 Need Help?

1. **Read** [DEVELOPMENT.md](DEVELOPMENT.md) - Detailed troubleshooting
2. **Check** [GitHub issues](https://github.com/RPi-Distro/python-sense-emu/issues)
3. **Consult docs** at [sense-emu.readthedocs.io](https://sense-emu.readthedocs.io)

---

**Version:** 1.0.0 | **Date:** 2026-06-07 | **Platforms:** Windows, Linux, macOS
