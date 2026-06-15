FROM python:3.12-slim

# Install PostgreSQL 16 + pgvector + system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gnupg2 curl ca-certificates lsb-release git \
    && echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
       > /etc/apt/sources.list.d/pgdg.list \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
       | gpg --dearmor -o /etc/apt/trusted.gpg.d/pgdg.gpg \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       postgresql-16 postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cache-bust: force Docker to rebuild all layers after this point
RUN echo "cache-bust-v2-2026-06-15-02" > /dev/null

# Copy backend code
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini .
COPY backend/main.py .

# Copy pre-built frontend
COPY backend/static ./static

# Startup script
COPY deploy/start.sh /start.sh
RUN chmod +x /start.sh

# HF Spaces uses port 7860
EXPOSE 7860

# Use /data for persistent storage (HF Spaces mounts this)
ENV PGDATA=/data/pgdata
ENV DATABASE_URL=postgresql+asyncpg://devbuddy:devbuddy@localhost:5432/devbuddy

CMD ["/start.sh"]
