# syntax=docker/dockerfile:1
#
# Build from the repo root (this is a uv workspace — openclaw-runtime
# depends on the sibling libs/auth package, so the whole workspace
# manifest tree has to be present to resolve, even though only this
# service's own dependencies actually get installed):
#   docker build -f services/openclaw-runtime/Dockerfile -t staffstream/openclaw-runtime .
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY libs/ libs/
COPY services/ services/

RUN uv sync --frozen --no-dev --package openclaw-runtime

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8006

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8006/healthz', timeout=3)" || exit 1

CMD ["uvicorn", "openclaw_runtime.main:app", "--host", "0.0.0.0", "--port", "8006", "--app-dir", "services/openclaw-runtime/src"]
