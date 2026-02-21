FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir "."

COPY . .

# Cloud Run injects $PORT (default 8080); fall back to 8000 for local docker run
CMD exec uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
