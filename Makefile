.PHONY: api streamlit test test-all lint format install clean

install:
	pip install -e ".[dev]"

api:
	@bash scripts/start-api.sh

streamlit:
	streamlit run src/ui/app.py --server.port $${STREAMLIT_PORT:-8501}

test:
	pytest tests/ -v -m "not expensive"

test-all:
	pytest tests/ -v

lint:
	ruff check src/ tests/
	mypy src/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
