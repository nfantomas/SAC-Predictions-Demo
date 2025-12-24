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
poetry run python -m demo.refresh --source fixture
poetry run python -m demo.query
poetry run python -m demo.forecast
poetry run python -m demo.run
poetry run python -m demo.scenarios
poetry run python -m demo.smoke_scenarios
poetry run ruff check .
```

### What each command does
- `poetry run pytest -q`: runs all unit tests (offline, uses fixtures and mocks).
- `poetry run python -m demo.auth_check`: validates OAuth token acquisition and a DES connectivity check.
- `poetry run python -m demo.des_check`: runs the DES “Namespaces” probe only (connectivity/permissions).
- `poetry run python -m demo.refresh --source sac`: pulls the locked dataset slice, normalizes, and writes cache.
- `poetry run ruff check .`: runs lint checks.

### How to verify everything works end-to-end
1) `poetry run python -m demo.auth_check` → expect `OK <timestamp>` and `DES OK`
2) `poetry run python -m demo.refresh --source sac` → expect cache written and `CACHE_META` summary
3) `poetry run pytest -q` → all green for unit tests

## MCP Server (minimal)
Start the server:
```bash
poetry run python -m mcp_server --host 127.0.0.1 --port 8080
```

List tools:
```bash
curl -s http://127.0.0.1:8080/tools
```

Health:
```bash
curl -s -X POST http://127.0.0.1:8080/health
```

Get timeseries from cache:
```bash
curl -s -X POST http://127.0.0.1:8080/get_timeseries \
  -H "Content-Type: application/json" \
  -d '{"from_cache": true, "start": "2020-01-01", "end": "2020-12-01"}'
```
