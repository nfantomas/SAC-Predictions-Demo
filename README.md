# SAC Predictions Demo

## Local Setup (Poetry + venv)
Prereqs: Python 3.11+ and Poetry installed.

Use Poetry for all installs and commands. This repo uses an in-project virtualenv
located at `.venv/`.

```bash
poetry config virtualenvs.in-project true
poetry install
poetry check
poetry run pytest -q
poetry run python -m demo.smoke
```

## Common Commands
```bash
poetry run pytest -q
poetry run python -m demo.auth_check
poetry run python -m demo.des_check
poetry run python -m demo.refresh --source sac
poetry run ruff check .
```
