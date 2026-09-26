# AI Coding Harness - standardised evaluation interface.
# The evaluator will run: export AI_API_KEY=... && make setup && make run

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: setup run test clean lint typecheck

setup:
	@echo ">> Setting up environment..."
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	@echo ">> Verifying environment..."
	@$(PYTHON) -m harness doctor || true
	@echo ">> Setup complete."

run:
	@echo ">> Launching AI Harness..."
	$(PYTHON) -m harness run

test:
	$(PYTHON) -m pytest

lint:
	$(VENV)/bin/ruff check src tests
	$(VENV)/bin/ruff format --check src tests

typecheck:
	$(VENV)/bin/mypy

clean:
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml htmlcov dist build *.egg-info src/*.egg-info
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo ">> Cleaned."
