# Local CI/CD Testing

Guide to run the same CI tests locally before pushing to GitHub.

## 🚀 Quick Start

### Install testing tools

```bash
# Activate your venv first
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install testing dependencies
pip install -e ".[test]"
pip install pre-commit
```

### Run pre-commit checks

```bash
# Install pre-commit hooks (runs on every commit)
pre-commit install

# Run all checks on changed files
pre-commit run --all-files

# Run specific check
pre-commit run black --all-files
pre-commit run mypy --all-files
pre-commit run flake8 --all-files
```

### Run pytest locally

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=sense_emu --cov-report=html --cov-fail-under=85

# Run specific test file
pytest tests/test_sense_hat.py -v

# Run with verbose output
pytest -vv

# Run in parallel (faster)
pip install pytest-xdist
pytest -n auto
```

## 📊 Full CI Simulation

To simulate the exact GitHub Actions workflow:

### Python 3.13 full test

```bash
# Create Python 3.13 venv
python3.13 -m venv venv-py313
source venv-py313/bin/activate  # Linux/Mac
venv-py313\Scripts\activate     # Windows

# Install and test
pip install -e ".[gui,test]"

# Run tests exactly as CI does
pytest \
  --cov=sense_emu \
  --cov-report=term-missing \
  --cov-report=xml \
  --cov-report=html \
  --cov-fail-under=85 \
  -v \
  --tb=short
```

### Python 3.14 test (if available)

```bash
python3.14 -m venv venv-py314
source venv-py314/bin/activate
pip install -e ".[gui,test]"
pytest --cov=sense_emu --cov-fail-under=85 -v
```

### Test with warnings as errors

```bash
pytest \
  -W error::DeprecationWarning \
  -W error::PendingDeprecationWarning \
  -v
```

### Security checks

```bash
# Install security tools
pip install bandit safety

# Run Bandit (security issues)
bandit -r sense_emu/ -ll

# Check known vulnerabilities
safety check
```

## 🔍 Pre-commit Hooks

### What it does

The `.pre-commit-config.yaml` file configures:
- **Black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **bandit**: Security scanning
- **pydocstyle**: Docstring style

### Install pre-commit

```bash
pip install pre-commit

# Install the git hooks
pre-commit install

# Now pre-commit runs on every commit
```

### Run manually

```bash
# Check all files
pre-commit run --all-files

# Check only changed files
pre-commit run

# Check specific hook
pre-commit run black --all-files
```

### Bypass pre-commit (not recommended)

```bash
# Skip pre-commit checks (dangerous!)
git commit --no-verify
```

## 📈 Coverage Analysis

### View coverage report

```bash
# Generate HTML report
pytest --cov=sense_emu --cov-report=html

# Open in browser
# Windows
start htmlcov/index.html
# Linux
xdg-open htmlcov/index.html
# Mac
open htmlcov/index.html
```

### Find uncovered lines

```bash
# Show coverage in terminal
pytest --cov=sense_emu --cov-report=term-missing

# Find lines not covered
grep -r "NOCOV" sense_emu/  # Lines deliberately not covered
```

## 🐛 Debugging Failed Tests

### Run single test

```bash
pytest tests/test_sense_hat.py::TestSenseHat::test_init -vv
```

### Run with more details

```bash
# Show print statements
pytest -s

# Show full diffs
pytest --tb=long

# Drop into debugger on failure
pytest --pdb

# Drop into debugger on error
pytest --pdbcls=IPython.terminal.debugger:Pdb
```

### Run tests with warnings

```bash
# Show all warnings
pytest -W all

# Treat warnings as errors
pytest -W error
```

## 🔄 Multi-version Testing

### Using tox (test multiple Python versions)

```bash
# Install tox
pip install tox

# Create tox.ini in project root
cat > tox.ini << 'EOF'
[tox]
envlist = py38,py39,py310,py311,py312,py313,py314

[testenv]
deps = .[test]
commands = pytest --cov=sense_emu --cov-fail-under=85
EOF

# Run all environments
tox

# Run specific version
tox -e py313

# Run in parallel
tox -p
```

## 📋 Checklist Before Push

```bash
# 1. Format code
pre-commit run --all-files

# 2. Run tests
pytest --cov=sense_emu --cov-fail-under=85 -v

# 3. Check coverage
pytest --cov=sense_emu --cov-report=term-missing

# 4. Run type check
mypy sense_emu --ignore-missing-imports

# 5. Security check
bandit -r sense_emu/ -ll

# 6. All good, push!
git push
```

## 🚨 Common CI Failures

### "Coverage is X%, required 85%"

Add missing test coverage:
```bash
# See which lines aren't covered
pytest --cov=sense_emu --cov-report=term-missing

# Find and test those code paths
# Then add tests to tests/
```

### "Black would reformat ..."

Let Black fix it:
```bash
black sense_emu/
```

### "Mypy found type errors"

Fix type hints:
```bash
mypy sense_emu --ignore-missing-imports
```

### "Test failed on Python 3.14"

Test locally with Python 3.14:
```bash
python3.14 -m venv venv-py314
source venv-py314/bin/activate
pip install -e ".[test]"
pytest -vv
```

## 🎯 GitHub Actions Badges

Add to your README:

```markdown
# Status Badges

![Tests](https://github.com/RPi-Distro/python-sense-emu/workflows/Tests/badge.svg)
![Python 3.13 & 3.14](https://github.com/RPi-Distro/python-sense-emu/workflows/Python%203.13%20%26%203.14%20Tests/badge.svg)
[![codecov](https://codecov.io/gh/RPi-Distro/python-sense-emu/branch/main/graph/badge.svg)](https://codecov.io/gh/RPi-Distro/python-sense-emu)
```

## 📚 Documentation

- [GitHub Actions](https://docs.github.com/en/actions)
- [Pre-commit](https://pre-commit.com/)
- [Pytest](https://docs.pytest.org/)
- [Coverage.py](https://coverage.readthedocs.io/)
- [Black](https://black.readthedocs.io/)
- [mypy](https://mypy.readthedocs.io/)

## 💡 Pro Tips

### Speed up testing

```bash
# Run tests in parallel
pip install pytest-xdist
pytest -n auto

# Run only changed tests
pip install pytest-testmon
pytest --testmon
```

### Cache pip downloads

```bash
# Use pip's cache
pip install --cache-dir ~/.pip-cache -e ".[test]"
```

### Skip slow tests

```bash
pytest -m "not slow"
```

### Watch for changes

```bash
pip install pytest-watch
ptw  # Runs tests when files change
```

---

**All tests should pass locally before pushing to GitHub!**

**Last updated:** 2026-06-07
