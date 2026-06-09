# Release Process

This document describes how to create and publish a new release of `sense-emu`.

## Prerequisites

Install the required build tools once:

```bash
pip install build twine
```

## Steps

### 1. Prepare the release

Decide on the new version number following [Semantic Versioning](https://semver.org/):
- **Patch** (`1.2.x`): Bug fixes, no new features.
- **Minor** (`1.x.0`): New backward-compatible features.
- **Major** (`x.0.0`): Breaking changes.

### 2. Bump the version

Update the version string in **two places** (they must match):

- `sense_emu/__init__.py` — `__version__` variable
- `pyproject.toml` — `version` field under `[project]`

Example:
```bash
# sense_emu/__init__.py
__version__ = '1.3.0'

# pyproject.toml
version = "1.3.0"
```

### 3. Update the changelog

Add an entry to `docs/changelog.rst` describing what changed.

### 4. Run the full test suite

```bash
pytest
```

All tests must pass and coverage must stay at or above 85 %.

### 5. Commit and tag

```bash
git add sense_emu/__init__.py pyproject.toml docs/changelog.rst
git commit -m "Release v1.3.0"
git tag -a v1.3.0 -m "Release v1.3.0"
git push origin main --tags
```

### 6. Build the distribution

```bash
# Remove any previous builds
rm -rf dist/ build/ *.egg-info

# Build source distribution and wheel
python -m build
```

This produces two files in `dist/`:
- `sense_emu-1.3.0.tar.gz` — source distribution
- `sense_emu-1.3.0-py3-none-any.whl` — wheel

### 7. Verify the build

```bash
# Check the distributions for common issues
twine check dist/*

# Optional: install in a clean venv and smoke-test
python -m venv /tmp/test-release
/tmp/test-release/bin/pip install dist/sense_emu-1.3.0-py3-none-any.whl
/tmp/test-release/bin/python -c "from sense_emu import SenseHat; print('OK')"
```

### 8. Publish to PyPI

Upload to [PyPI](https://pypi.org/):

```bash
twine upload dist/*
```

You will be prompted for your PyPI credentials (or API token — recommended).
To use an API token add it to `~/.pypirc`:

```ini
[pypi]
username = __token__
password = pypi-AgEIcH...
```

### 9. Publish to TestPyPI first (optional but recommended)

```bash
twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ sense-emu==1.3.0
```

### 10. Create a GitHub Release

After the tag is pushed, create a GitHub release:

```bash
# Using the GitHub CLI
gh release create v1.3.0 dist/* \
  --title "v1.3.0" \
  --notes "See docs/changelog.rst for details."
```

Or do it manually on the GitHub Releases page.

---

## Rollback

If a bad release is published:

1. **Yank** the broken version on PyPI (it stays available but is hidden from searches):
   - Go to <https://pypi.org/manage/project/sense-emu/releases/>
   - Click the version → "Yank release"

2. Fix the issue, bump to the next patch version, and repeat the process.

---

## CI Automation

The `.github/workflows/publish.yml` workflow can publish automatically when a
tag matching `v*` is pushed. Make sure the `PYPI_API_TOKEN` secret is configured
in the repository settings before using it.
