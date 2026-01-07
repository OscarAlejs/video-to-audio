FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir --upgrade yt-dlp

COPY app/ ./app/
COPY cookies.tx[t] ./

RUN chown -R appuser:appuser /app && chmod -R 755 /app

RUN mkdir -p /tmp/video-to-audio && chown appuser:appuser /tmp/video-to-audio

USER appuser

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
