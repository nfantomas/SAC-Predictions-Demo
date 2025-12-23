.PHONY: setup check test smoke lint

setup:
	poetry config virtualenvs.in-project true
	poetry install

check:
	poetry check

test:
	poetry run pytest -q

smoke:
	poetry run python -m demo.smoke

lint:
	poetry run ruff check .
