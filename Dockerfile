# Citation Auditor — one command, no Python setup on the host.
#
# NOTE: pinned to 3.11-slim because 3.11 is the interpreter this stack has
# actually been run and tested against.
#
#   docker compose up --build      then open http://localhost:8000
#
# Runs with no credentials: every live component has an offline fallback, so
# the container is fully functional without an API key.

FROM python:3.11-slim

# curl is here only for the healthcheck below.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, so editing source does not invalidate the layer.
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# The SQLite store lives here. Mounted as a volume by compose so a loaded
# corpus survives a rebuild.
RUN mkdir -p data
ENV DATABASE_PATH=/app/data/auditor.db \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
