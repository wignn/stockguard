# Multi-stage production Dockerfile for StokGuard Backend & OCR
FROM python:3.12-slim-bookworm AS base

# System dependencies: Tesseract OCR with English and Indonesian models, curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-ind \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv for deterministic package installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    STOKGUARD_DATA_DIR=/app/data \
    STOKGUARD_TESSERACT_COMMAND=tesseract \
    STOKGUARD_OCR_LANGUAGES=eng+ind

# Install dependencies in virtual environment
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source and migrations
COPY . .
RUN uv sync --frozen --no-dev

# Put virtual environment in PATH
ENV PATH="/app/.venv/bin:$PATH"

# Make entrypoint executable and prepare data directory
RUN chmod +x /app/entrypoint.sh && mkdir -p /app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "stokguard.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
