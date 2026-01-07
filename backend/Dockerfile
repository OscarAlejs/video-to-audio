# Backend - Video to Audio API
FROM python:3.12-slim

# Instalar ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Usuario no-root
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código
COPY app/ ./app/
COPY cookies.tx[t] ./

# Directorio temporal
RUN mkdir -p /tmp/video-to-audio && chown appuser:appuser /tmp/video-to-audio

USER appuser

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
