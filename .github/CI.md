# Continuous Integration (CI) Setup

Automated testing for the Sense HAT Emulator using GitHub Actions.

## 🔄 Workflows

### 1. **tests.yml** - Main Test Suite
Runs on every push and pull request to `main` and `develop` branches.

**Configuration:**
- **Python versions**: 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14
- **Operating systems**: Ubuntu, Windows, macOS
- **Matrix**: Tests all combinations (with some exclusions to save CI time)

**Jobs:**
1. **test** - Run pytest with coverage
   - Installs dependencies
   - Runs tests: `pytest --cov=sense_emu --cov-report=xml`
   - Uploads coverage to Codecov
   - Checks coverage ≥85%

2. **compatibility** - Full test run on Python 3.13
   - Runs on main branch pushes only
   - Verifies all tests pass

3. **type-check** - Optional mypy type checking
   - Runs mypy for type hints
   - Non-blocking (continues on error)

4. **build** - Package building
   - Builds distribution packages
   - Uploads artifacts

### 2. **python-313-314.yml** - Focused Testing
Dedicated testing for Python 3.13 and 3.14 (new versions).

**Configuration:**
- **Python versions**: 3.13, 3.14
- **Operating systems**: Ubuntu, Windows, macOS
- **Runs daily** (5 AM UTC) to catch compatibility issues

**Jobs:**
1. **test-py313-py314** - Comprehensive testing
   - Tests latest Python versions
   - Generates HTML coverage reports
   - Uploads to Codecov

2. **test-with-warnings** - Strict warnings check
   - DeprecationWarnings treated as errors
   - Ensures forward compatibility

3. **security-check** - Security analysis
   - Bandit: Security issue scanner
   - Safety: Known vulnerabilities check

4. **performance** - Performance baseline
   - Runs on main pushes
   - Optional pytest-benchmark

## 📊 Coverage Requirements

- **Minimum**: 85% (hard requirement)
- **Current**: 91.67% ✅

Coverage is checked in:
- `test` job: Optional warning if <85%
- `test-py313-py314` job: Hard requirement (fails if <85%)

Coverage reports are uploaded to Codecov for tracking over time.

## 🎯 What Gets Tested

Each workflow run executes:

```bash
pytest \
  --cov=sense_emu \
  --cov-report=term-missing \
  --cov-report=xml \
  --cov-fail-under=85 \
  -v
```

This covers:
- ✅ All 427 tests pass
- ✅ Code coverage ≥85%
- ✅ Works on Python 3.8-3.14
- ✅ Works on Windows, Linux, macOS

## ⚙️ Configuration Details

### Caching
- Uses GitHub's built-in pip cache
- Speeds up subsequent runs

### Fail-Fast
Set to `false` - continues testing all combinations even if one fails.

### Artifacts
- Coverage HTML reports (uploaded for each Python version)
- Built packages (wheel and source dist)

## 🔔 Notifications

GitHub automatically notifies:
- Status checks on PR commits
- Email on failed tests (if enabled in repo settings)
- Badge in README showing current status

## 📈 Codecov Integration

Coverage reports are uploaded to Codecov for:
- Historical tracking
- Pull request comparison
- Badge generation
- Coverage trends

View at: `https://codecov.io/gh/RPi-Distro/python-sense-emu`

## 🚀 Local Testing (Simulate CI)

To run the same tests locally:

```bash
# Python 3.13
python3.13 -m venv venv
source venv/bin/activate
pip install -e ".[gui,test]"
pytest --cov=sense_emu --cov-fail-under=85 -v

# Python 3.14
python3.14 -m venv venv314
source venv314/bin/activate
pip install -e ".[gui,test]"
pytest --cov=sense_emu --cov-fail-under=85 -v
```

## 🔐 Security

The workflows include:
- No secrets stored in code
- No external credential access
- Bandit security scanning
- Safety vulnerability checking

## 📝 Adding New Workflows

To add a new workflow:

1. Create `.github/workflows/new-workflow.yml`
2. Define trigger events (push, pull_request, schedule)
3. Configure matrix for Python versions/OS
4. Define job steps
5. Push to repository - GitHub auto-discovers it

## 🛠️ Troubleshooting

### Tests fail in CI but pass locally

Common causes:
- **Different Python version** - CI tests 3.8-3.14, local might be 3.12
- **OS difference** - Test passes on Linux but fails on Windows
- **Race conditions** - mmap file cleanup between tests

Solution:
```bash
# Test with Python 3.13
python3.13 -m pytest -v

# Test with stricter conditions
pytest --tb=short -v
```

### Coverage check fails

```bash
# Check coverage locally
pytest --cov=sense_emu --cov-report=term-missing

# If <85%, add missing tests
```

### Build artifacts missing

Check that `pip install -e ".[gui,test]"` succeeds. If not:
```bash
pip install --upgrade pip setuptools wheel
pip install -e ".[gui,test,build]"
```

## 📚 Further Reading

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Codecov Documentation](https://docs.codecov.io)
- [Pytest Documentation](https://docs.pytest.org)
- [Coverage.py Documentation](https://coverage.readthedocs.io)

---

**Last updated:** 2026-06-07
**Status:** ✅ All tests passing on Python 3.8-3.14
**Coverage:** 91.67% (requirement: 85%)
