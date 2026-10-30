# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install curl for container health check
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install runtime dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user and logs directory
RUN useradd -u 10001 -m -s /bin/bash appuser && \
    mkdir -p logs && \
    chown -R appuser:appuser /app

# Copy application source code and scripts
COPY --chown=appuser:appuser app/ app/
COPY --chown=appuser:appuser scripts/ scripts/

# Build arguments for git SHA tracking
ARG GIT_SHA=""
ENV GIT_SHA=${GIT_SHA}

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
