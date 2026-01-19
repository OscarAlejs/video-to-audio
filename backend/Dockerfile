FROM python:3.12-slim

# Install base dependencies (without nodejs - we'll install a newer version)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    nginx \
    supervisor \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x LTS from NodeSource (required for yt-dlp JS challenge solving)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp-ejs globally for YouTube JS challenge solving
RUN npm install -g yt-dlp-ejs@latest

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY cookies.tx[t] ./
# Copiar configuración de nginx a múltiples ubicaciones posibles
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
RUN rm -f /etc/nginx/conf.d/default.conf.bak 2>/dev/null || true

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
command=uvicorn app.main:app --host 127.0.0.1 --port 8001 --timeout-keep-alive 900\n\
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
