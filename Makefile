.PHONY: install test lint typecheck check backtest validate

install:
	python3 -m venv .venv
	.venv/bin/python -m pip install -e ".[dev]"

test:
	.venv/bin/python -m pytest

lint:
	.venv/bin/python -m ruff check .

typecheck:
	.venv/bin/python -m pyright

check: lint typecheck test

backtest:
	.venv/bin/quant backtest --strategy momentum --data data/sample_prices.csv --symbol AAPL

validate:
	.venv/bin/quant data validate --data data/sample_prices.csv --symbol AAPL --min-rows 2
