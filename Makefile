PYTHON ?= .venv/bin/python
.PHONY: setup fetch pipeline reproduce test serve clean-help
setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt
	Rscript scripts/setup_R.R
fetch:
	Rscript scripts/fetch_data.R
pipeline:
	$(PYTHON) scripts/run_pipeline.py
reproduce: fetch pipeline test
test:
	$(PYTHON) -m unittest discover -s tests -v
	node --test tests/frontend.test.mjs
	node --check dist/app.js
serve:
	$(PYTHON) -m http.server 4173 --bind 127.0.0.1 --directory dist
