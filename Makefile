# Shortcuts for the commands in README.md. Override the run folder: make run OUT=/tmp/run1
# OUT holds what learners typed (personal data until stage 1): keep it outside the repository.
OUT ?= /tmp/institution_mapping/out
PY  ?= python3

.PHONY: install run test lint quality release

install:            ## the package and the development tools
	$(PY) -m pip install -e ".[dev]"

run:                ## the whole mapping (about 30 minutes): input from input/ and output/, coding from coding/
	$(PY) -m institution_mapping run $(OUT)

test:               ## unit tests; with a run: also the regression and decision tests
	IM_RUN_DIR=$(OUT) $(PY) -m pytest -q

lint:
	ruff check src tests tools

quality:            ## the code-quality measures of docs/qa/code_quality.md
	ruff check src --statistics || true
	radon cc src -a -s --total-average | tail -3
	radon mi src -s | sort -k3 | head -5
	interrogate src | tail -1

release:            ## copy the run's register, workbook and reference into the repository
	$(PY) -m institution_mapping release $(OUT)
