# Python 3.11 to match the version this service is developed and tested against; the
# image previously specified 3.9, which nothing ever ran.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# The repo layout is mirrored inside the image so that requirements.txt's
# `-e ../../shared` resolves to /app/shared, exactly as it resolves to the repo's
# shared/ during local development. One relative path, one source of truth.
COPY shared/ ./shared/
COPY platforms/organization-service/requirements.txt ./platforms/organization-service/

WORKDIR /app/platforms/organization-service
RUN pip install --no-cache-dir -r requirements.txt

# Application code and the migration tooling, so `alembic upgrade head` can run from the image
COPY platforms/organization-service/src/ ./src/
COPY platforms/organization-service/alembic/ ./alembic/
COPY platforms/organization-service/alembic.ini ./alembic.ini

EXPOSE 8000

CMD ["uvicorn", "src.organization.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
