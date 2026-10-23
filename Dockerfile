FROM python:3.11-slim AS base

RUN apt-get update && \
    apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-tur curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV ENVIRONMENT=production

COPY . .

RUN mkdir -p /app/data/history /app/data/audit /app/data/backups /app/data/notifications /app/data/templates /app/data/auth /app/data/logs /app/uploads && \
    adduser --disabled-password --no-create-home appuser && \
    chown -R appuser:appuser /app /app/data /app/uploads

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--access-log"]
