FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as non-root user for security
RUN adduser --disabled-password --no-create-home appuser
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD ["python", "-c", "import httpx; httpx.get('http://localhost:8080/health').raise_for_status()"]

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
