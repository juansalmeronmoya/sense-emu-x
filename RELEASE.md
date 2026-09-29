# Release Process

How to publish a new release of `sense-emu-x` (import name: `sense_emu`).

Publishing is automated: creating a **GitHub Release** triggers
`.github/workflows/publish.yml`, which builds the sdist/wheel, publishes to
TestPyPI and then to PyPI using
[trusted publishing](https://docs.pypi.org/trusted-publishers/) (OIDC). No API
token is stored in the repository.

## One-time setup

1. On PyPI and TestPyPI, register the project `sense-emu-x` and add a
   *trusted publisher* pointing at this repository, workflow `publish.yml`,
   and environments `pypi` / `testpypi` respectively.
2. Create the GitHub environments `pypi` and `testpypi` in the repository
   settings (optionally require manual approval on `pypi`).

## Steps

### 1. Choose the version

Follow [Semantic Versioning](https://semver.org/):

- **Patch** (`x.y.Z`): bug fixes only.
- **Minor** (`x.Y.0`): backward-compatible features.
- **Major** (`X.0.0`): breaking changes (for example, a change in the units
  returned by the API).

### 2. Bump the version (one place only)

Edit `__version__` in `sense_emu/__init__.py`. `pyproject.toml` reads it
dynamically, so there is nothing else to keep in sync.

### 3. Update the changelog

Add an entry to `docs/changelog.rst`, calling out any breaking fix explicitly.

### 4. Verify locally

```bash
pip install -e ".[gui,tui,test]"
pytest
python -m build
twine check dist/*
```

### 5. Commit and tag

```bash
git add sense_emu/__init__.py docs/changelog.rst
git commit -m "Release vX.Y.Z"
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin master --tags
```

### 6. Create the GitHub Release

Publish a release for the tag (GitHub UI or `gh release create vX.Y.Z`).
The `Publish to PyPI` workflow runs automatically: build → TestPyPI → PyPI.

### 7. Smoke-test the published package

```bash
python -m venv /tmp/release-check
/tmp/release-check/bin/pip install "sense-emu-x[gui]"
/tmp/release-check/bin/python -c "from sense_emu import SenseHat; print('OK')"
```

## Rollback

If a bad release is published, **yank** it on PyPI
(<https://pypi.org/manage/project/sense-emu-x/releases/> → *Yank release*),
fix the problem, bump the patch version and release again.
