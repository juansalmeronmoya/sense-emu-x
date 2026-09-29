# Continuous integration

A single workflow, `.github/workflows/ci.yml`, runs on every pull request, on
pushes to `master`, weekly (Mondays 03:00 UTC) and on demand.

| Job | Runs on | What it does |
|-----|---------|--------------|
| `lint` | ubuntu | `ruff check .` (rules in `pyproject.toml`). Blocking. |
| `test` | ubuntu, windows, macos × Python 3.11, 3.12, 3.13, 3.14 | `pip install -e ".[gui,tui,test]"` then `pytest`. Qt runs headless (`QT_QPA_PLATFORM=offscreen`, set in `setup.cfg`). Fails if coverage drops below the threshold in `setup.cfg`. Uploads `coverage.xml`. |
| `build` | ubuntu | `python -m build` + `twine check`; uploads the wheel and sdist as an artifact. |

Releases are published by `.github/workflows/publish.yml` when a GitHub Release
is created (build → TestPyPI → PyPI via trusted publishing). See
[`RELEASE.md`](../RELEASE.md).

## Supported versions

Python **3.11 – 3.14** on Linux, Windows and macOS. The minimum follows the
oldest CPython release that still receives security fixes; raise
`requires-python` in `pyproject.toml`, the `test` matrix and the classifiers
together when a version reaches end of life.

## Planned (see `docs/PLAN_REVISION.md`)

- Type checking (`mypy`) as a blocking job once the codebase is annotated.
- `ruff format --check` once the code has been reformatted in one dedicated commit.
- Combined cross-platform coverage report with a global threshold.
- PyInstaller bundles attached to releases.
