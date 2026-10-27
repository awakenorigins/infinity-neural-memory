.PHONY: help install verify test build demo lint clean
help:
	@echo "make install   - editable install with dev deps"
	@echo "make verify    - run VERIFY.py (real features must pass)"
	@echo "make test      - run pytest"
	@echo "make demo      - run the end-to-end example"
	@echo "make build     - build wheel + sdist into dist/"
	@echo "make clean     - remove build/test artifacts"

install:
	pip install -e ".[dev]"

verify:
	python VERIFY.py

test:
	pytest tests/ -q

demo:
	python examples/demo.py

build:
	python -m build

clean:
	rm -rf build dist *.egg-info .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	find . -name '*.pyc' -delete
