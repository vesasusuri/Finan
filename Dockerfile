# Render — single service: React frontend + FastAPI API on one URL.
# Local Compose still uses backend/Dockerfile (API only).

FROM node:20-alpine AS frontend-build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
COPY DOCS/branding/ /branding/
ENV VITE_BRANDING_DIR=/branding
# Same origin — browser calls /api/* on this host (no cross-origin cookies).
ENV VITE_API_BASE_URL=

RUN npm run build

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=frontend-build /app/dist /app/frontend_dist

ENV FRONTEND_STATIC_PATH=/app/frontend_dist

RUN mkdir -p /data/uploads /var/log/borek

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
