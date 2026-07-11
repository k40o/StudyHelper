# --- Stage 1: build the React frontend ---
FROM node:20-alpine AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python backend that also serves the built frontend ---
FROM python:3.12-slim AS app
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VECTOR_STORE=simple \
    STUDYGAME_DATA_DIR=/data \
    STUDYGAME_MATERIALS_DIR=/data/StudyMaterials \
    STUDYGAME_FRONTEND_DIST=/app/frontend/dist

COPY backend/requirements-deploy.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY backend/app ./app
COPY --from=frontend /fe/dist ./frontend/dist

# Persistent data (SQLite DB, uploaded materials, vector index) lives here.
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000
# Cloud hosts inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
