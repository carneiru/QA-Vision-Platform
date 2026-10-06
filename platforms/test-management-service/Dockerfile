FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# The repo layout is mirrored inside the image so that requirements.txt's
# `-e ../../shared` resolves to /app/shared, exactly as it does in a checkout.
COPY shared/ ./shared/
COPY platforms/test-management-service/requirements.txt ./platforms/test-management-service/

WORKDIR /app/platforms/test-management-service
RUN pip install --no-cache-dir -r requirements.txt

COPY platforms/test-management-service/src/ ./src/
COPY platforms/test-management-service/alembic/ ./alembic/
COPY platforms/test-management-service/alembic.ini ./alembic.ini

EXPOSE 8000

CMD ["uvicorn", "src.casebook.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
