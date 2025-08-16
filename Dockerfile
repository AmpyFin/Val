# Multi-arch light image
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps that some libs (pandas/yfinance) like
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install -r requirements.txt

# App code
COPY . .

# Where results are written/read
VOLUME ["/app/out"]

# API port
EXPOSE 8000

# Default = API server (writer runs via docker-compose service)
CMD ["uvicorn", "server.api:app", "--host", "0.0.0.0", "--port", "8000"]
