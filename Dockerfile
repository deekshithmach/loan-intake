# Backend image (FastAPI). Build context = repo root, because the code imports as `apps.api...`.
#   docker build -t ledgerly-api .
#   docker run -p 8000:8000 -e DATABASE_URL=... -e GEMINI_API_KEY=... ledgerly-api
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH"
WORKDIR /app

# Dependencies first so this layer is cached until pyproject/uv.lock change.
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Only the API code. datagen/evals/tests/UI stay out (see .dockerignore).
COPY apps/api ./apps/api
COPY apps/__init__.py ./apps/__init__.py

# Uploaded PDFs live here; mount a persistent disk/volume at this path (set UPLOADS_DIR to match).
RUN useradd --create-home app && mkdir -p /data/uploads && chown -R app /data /app
ENV UPLOADS_DIR=/data/uploads
USER app

EXPOSE 8000
# Hosts like Render/Fly inject $PORT; default 8000 for local runs.
CMD ["sh", "-c", "uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
