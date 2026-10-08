PYTHON ?= .venv/bin/python

.PHONY: check
check:
	$(PYTHON) -m ruff check job_records tests
	$(PYTHON) -m ruff format --check job_records tests
	$(PYTHON) -m mypy
	$(PYTHON) -m unittest discover -s tests -q
