# Production image: Vite/React UI + FastAPI (for Render, Fly, etc.)
# Build: docker build -t dcn-demo .
# Run:  docker run -e DATABASE_URL=... -e BASE_URL=... -p 8000:8000 dcn-demo

FROM node:20-bookworm-slim AS frontend
WORKDIR /app/frontend/web
COPY frontend/web/package.json frontend/web/package-lock.json ./
RUN npm ci
COPY frontend/web/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY --from=frontend /app/frontend/web/dist /app/frontend/web/dist

WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
