FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir --upgrade yt-dlp

COPY app/ ./app/
COPY cookies.tx[t] ./
COPY nginx.conf /etc/nginx/sites-available/default

# Supervisor config para correr nginx + uvicorn
RUN echo '[supervisord]\n\
nodaemon=true\n\
user=root\n\
\n\
[program:nginx]\n\
command=/usr/sbin/nginx -g "daemon off;"\n\
autostart=true\n\
autorestart=true\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile=/dev/stderr\n\
stderr_logfile_maxbytes=0\n\
\n\
[program:uvicorn]\n\
command=uvicorn app.main:app --host 127.0.0.1 --port 8001 --timeout-keep-alive 900 --timeout-graceful-shutdown 900\n\
autostart=true\n\
autorestart=true\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile=/dev/stderr\n\
stderr_logfile_maxbytes=0\n\
' > /etc/supervisor/conf.d/supervisord.conf

RUN mkdir -p /tmp/video-to-audio && chmod 777 /tmp/video-to-audio

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
