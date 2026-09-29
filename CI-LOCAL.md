# Running the CI checks locally

Mirror of the jobs in `.github/workflows/ci.yml`.

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[gui,tui,test]" ruff build twine

ruff check .                 # lint job
pytest                       # test job (headless Qt via setup.cfg)
python -m build && twine check dist/*   # build job
```

On Linux you may need the Qt runtime libraries that the CI installs
(`libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 …`).

Optional: `pip install pre-commit && pre-commit install` runs `ruff` and the
basic file checks on every commit.

To test another Python version, create the virtualenv with that interpreter
(for example `python3.13 -m venv .venv`). Supported versions: 3.11 – 3.14.
