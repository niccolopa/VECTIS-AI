# VECTIS backend image.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# libgomp1 is required by XGBoost's runtime.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

COPY vectis ./vectis
COPY alembic.ini ./
COPY alembic ./alembic

# Sample data is mounted/seeded at runtime via the compose command; the repo
# data dir lives one level up in the compose context.
ENV VECTIS_DATA_DIR=/app/data \
    VECTIS_ARTIFACTS_DIR=/app/artifacts

EXPOSE 8000
CMD ["uvicorn", "vectis.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
