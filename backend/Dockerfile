FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY cookies.tx[t] ./

# Dar permisos al archivo de cookies
RUN chmod 644 /app/cookies.txt 2>/dev/null || true

RUN mkdir -p /tmp/video-to-audio && chown appuser:appuser /tmp/video-to-audio

USER appuser

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
