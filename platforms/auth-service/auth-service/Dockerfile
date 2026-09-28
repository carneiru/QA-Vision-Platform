# Python 3.11 to match the version this service is developed and tested against; the
# image previously specified 3.9, which nothing ever ran.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# The repo layout is mirrored inside the image so that requirements.txt's
# `-e ../../../shared` resolves to /app/shared, exactly as it resolves to the repo's
# shared/ during local development. One relative path, one source of truth.
COPY shared/ ./shared/
COPY platforms/auth-service/auth-service/requirements.txt ./platforms/auth-service/auth-service/

WORKDIR /app/platforms/auth-service/auth-service
RUN pip install --no-cache-dir -r requirements.txt

COPY platforms/auth-service/auth-service/src/ ./src/
COPY platforms/auth-service/auth-service/alembic/ ./alembic/
COPY platforms/auth-service/auth-service/alembic.ini ./alembic.ini

EXPOSE 8000

CMD ["python", "src/auth/main.py"]
