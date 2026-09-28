FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# The repo layout is mirrored inside the image so that requirements.txt's
# `-e ../../shared` resolves to /app/shared, exactly as it does in a checkout.
COPY shared/ ./shared/
COPY platforms/project-service/requirements.txt ./platforms/project-service/

WORKDIR /app/platforms/project-service
RUN pip install --no-cache-dir -r requirements.txt

COPY platforms/project-service/src/ ./src/
COPY platforms/project-service/alembic/ ./alembic/
COPY platforms/project-service/alembic.ini ./alembic.ini

EXPOSE 8000

CMD ["uvicorn", "src.project.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
