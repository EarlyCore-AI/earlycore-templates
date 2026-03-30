FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ARG INSTALL_PRESIDIO=true
RUN if [ "$INSTALL_PRESIDIO" = "true" ]; then \
        pip install --no-cache-dir presidio-analyzer presidio-anonymizer; \
    fi

COPY . .

RUN adduser --disabled-password --no-create-home sidecar
USER sidecar

EXPOSE 8443

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8443/health').raise_for_status()"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8443"]
