# Video to Audio API - Documentación

API REST para extraer audio de videos de YouTube y Vimeo.

**Base URL:** `https://videoconverter-api.8r3zyw.easypanel.host/api`

---

## Índice

1. [Resumen de Endpoints](#resumen-de-endpoints)
2. [Autenticación](#autenticación)
3. [Formatos y Calidades](#formatos-y-calidades)
4. [Endpoints](#endpoints)
   - [Health Check](#health-check)
   - [Video Info](#video-info)
   - [Process (Síncrono)](#process-síncrono)
   - [Process Download (Binario)](#process-download-binario)
   - [Extract (Asíncrono)](#extract-asíncrono)
   - [Jobs](#jobs)
   - [Logs](#logs)
5. [Casos de Uso](#casos-de-uso)
6. [Códigos de Error](#códigos-de-error)
7. [Ejemplos de Integración](#ejemplos-de-integración)

---

## Resumen de Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Estado del servicio |
| GET | `/info?url=` | Información del video |
| POST | `/process` | Procesar y obtener URL del audio |
| POST | `/process/download` | Procesar y obtener archivo binario |
| POST | `/extract` | Iniciar extracción asíncrona |
| GET | `/jobs` | Listar todos los jobs |
| GET | `/jobs/stats` | Estadísticas de jobs |
| GET | `/jobs/{job_id}` | Estado de un job específico |
| DELETE | `/jobs/{job_id}` | Eliminar un job |
| GET | `/logs` | Historial completo |
| GET | `/logs/api` | Historial de llamadas API |
| GET | `/logs/web` | Historial de uso web |
| GET | `/logs/errors` | Historial de errores |
| GET | `/logs/stats` | Estadísticas generales |
| POST | `/cleanup` | Limpiar archivos antiguos |

---

## Autenticación

Actualmente la API es pública y no requiere autenticación.

---

## Formatos y Calidades

### Formatos de Audio

| Formato | Descripción | Content-Type |
|---------|-------------|--------------|
| `mp3` | MPEG Audio Layer 3 (más compatible) | `audio/mpeg` |
| `m4a` | MPEG-4 Audio (mejor calidad/tamaño) | `audio/mp4` |
| `wav` | Waveform Audio (sin compresión) | `audio/wav` |
| `opus` | Opus Audio (mejor para streaming) | `audio/opus` |

### Calidades (Bitrate)

| Calidad | Bitrate | Uso Recomendado |
|---------|---------|-----------------|
| `128` | 128 kbps | Podcasts, voz |
| `192` | 192 kbps | Uso general (recomendado) |
| `256` | 256 kbps | Música casual |
| `320` | 320 kbps | Máxima calidad MP3 |

---

## Endpoints

### Health Check

Verifica el estado del servicio.

**Endpoint:** `GET /health`

**Respuesta:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "supabase_configured": true,
  "max_duration_minutes": 9999
}
```

**cURL:**
```bash
curl https://videoconverter-api.8r3zyw.easypanel.host/api/health
```

---

### Video Info

Obtiene información de un video sin descargarlo.

**Endpoint:** `GET /info?url={video_url}`

**Parámetros:**
| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `url` | string | Sí | URL del video (YouTube o Vimeo) |

**Respuesta:**
```json
{
  "id": "dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up",
  "duration_seconds": 212,
  "duration_formatted": "3:32",
  "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
  "source": "youtube",
  "channel": "Rick Astley"
}
```

**cURL:**
```bash
curl "https://videoconverter-api.8r3zyw.easypanel.host/api/info?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

---

### Process (Síncrono)

Procesa un video y devuelve la URL del audio en Supabase Storage.

**Cuándo usar:** Cuando necesitas el link permanente al audio.

**Endpoint:** `POST /process`

**Body:**
```json
{
  "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "format": "mp3",
  "quality": "192"
}
```

**Parámetros:**
| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `video_url` | string | Sí | - | URL del video |
| `format` | string | No | `mp3` | Formato de audio |
| `quality` | string | No | `192` | Bitrate en kbps |

**Respuesta Exitosa:**
```json
{
  "status": "success",
  "audio_url": "https://kfgpzdotqyympzklzkzz.supabase.co/storage/v1/object/public/audio-files/audio/20260108_123456_abc123_Rick_Astley.mp3",
  "video_info": {
    "id": "dQw4w9WgXcQ",
    "title": "Rick Astley - Never Gonna Give You Up",
    "duration_seconds": 212,
    "duration_formatted": "3:32",
    "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
    "source": "youtube",
    "channel": "Rick Astley"
  },
  "file_size": 5123456,
  "file_size_formatted": "4.89 MB",
  "duration": 212,
  "duration_formatted": "3:32",
  "format": "mp3",
  "quality": "192",
  "processing_time": 15.23,
  "message": "Audio extraído exitosamente"
}
```

**Respuesta Error:**
```json
{
  "status": "error",
  "error_code": "VIDEO_TOO_LONG",
  "message": "Video muy largo (120 min). Máximo: 60 min"
}
```

**cURL:**
```bash
curl -X POST "https://videoconverter-api.8r3zyw.easypanel.host/api/process" \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "format": "mp3", "quality": "192"}'
```

---

### Process Download (Binario)

Procesa un video y devuelve el archivo de audio directamente.

**Cuándo usar:** Cuando necesitas el archivo binario (para guardar, enviar por email, subir a otro servicio, etc.)

**Endpoint:** `POST /process/download`

**Body:**
```json
{
  "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "format": "mp3",
  "quality": "192"
}
```

**Respuesta:** Archivo binario de audio

**Headers de Respuesta:**
| Header | Descripción |
|--------|-------------|
| `Content-Type` | Tipo MIME del audio (ej: `audio/mpeg`) |
| `Content-Disposition` | Nombre del archivo para descarga |
| `Content-Length` | Tamaño en bytes |
| `X-Audio-URL` | URL de backup en Supabase |
| `X-Job-ID` | ID del job para referencia |
| `X-Video-Title` | Título del video |
| `X-Processing-Time` | Tiempo de procesamiento en segundos |
| `X-File-Size` | Tamaño formateado (ej: "4.89 MB") |

**cURL (descargar archivo):**
```bash
curl -X POST "https://videoconverter-api.8r3zyw.easypanel.host/api/process/download" \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "format": "mp3", "quality": "192"}' \
  --output audio.mp3
```

**cURL (ver headers + descargar):**
```bash
curl -X POST "https://videoconverter-api.8r3zyw.easypanel.host/api/process/download" \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "format": "mp3", "quality": "192"}' \
  -D - \
  --output audio.mp3
```

---

### Extract (Asíncrono)

Inicia extracción en background y devuelve un job_id para polling.

**Cuándo usar:** Para la interfaz web o cuando no quieres bloquear la conexión.

**Endpoint:** `POST /extract`

**Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "format": "mp3",
  "quality": "192"
}
```

**Nota:** Este endpoint usa `url` en lugar de `video_url`.

**Respuesta:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "progress": 0,
  "message": "Job creado",
  "created_at": "2026-01-08T12:00:00Z"
}
```

**Flujo de Polling:**
1. Llamar `POST /extract` → obtener `job_id`
2. Llamar `GET /jobs/{job_id}` cada 2 segundos
3. Cuando `status` sea `completed`, usar `result.audio_url`

**cURL:**
```bash
# 1. Iniciar extracción
curl -X POST "https://videoconverter-api.8r3zyw.easypanel.host/api/extract" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "format": "mp3", "quality": "192"}'

# 2. Verificar estado (reemplazar JOB_ID)
curl "https://videoconverter-api.8r3zyw.easypanel.host/api/jobs/JOB_ID"
```

---

### Jobs

#### Listar Jobs

**Endpoint:** `GET /jobs`

**Respuesta:**
```json
[
  {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "completed",
    "progress": 100,
    "message": "Completado",
    "created_at": "2026-01-08T12:00:00Z",
    "video_info": { ... },
    "result": {
      "audio_url": "https://...",
      "file_size": "4.89 MB"
    }
  }
]
```

#### Estadísticas de Jobs

**Endpoint:** `GET /jobs/stats`

**Respuesta:**
```json
{
  "total_jobs": 150,
  "completed_jobs": 140,
  "failed_jobs": 5,
  "active_jobs": 5
}
```

#### Obtener Job Específico

**Endpoint:** `GET /jobs/{job_id}`

**Estados posibles:**
| Status | Descripción |
|--------|-------------|
| `pending` | En cola |
| `processing` | Obteniendo info |
| `downloading` | Descargando video |
| `extracting` | Extrayendo audio |
| `uploading` | Subiendo a storage |
| `completed` | Finalizado exitosamente |
| `failed` | Error |

**Respuesta (completado):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 100,
  "message": "Completado",
  "created_at": "2026-01-08T12:00:00Z",
  "video_info": {
    "id": "dQw4w9WgXcQ",
    "title": "Rick Astley - Never Gonna Give You Up",
    "duration_seconds": 212,
    "duration_formatted": "3:32",
    "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
    "source": "youtube",
    "channel": "Rick Astley"
  },
  "result": {
    "success": true,
    "audio_url": "https://kfgpzdotqyympzklzkzz.supabase.co/storage/v1/object/public/audio-files/audio/...",
    "file_size": "4.89 MB",
    "format": "mp3",
    "quality": "192"
  }
}
```

#### Eliminar Job

**Endpoint:** `DELETE /jobs/{job_id}`

**Respuesta:**
```json
{
  "message": "Job eliminado"
}
```

---

### Logs

#### Historial Completo

**Endpoint:** `GET /logs?limit=50`

#### Historial API

**Endpoint:** `GET /logs/api?limit=50`

Solo jobs creados desde el endpoint `/process` o `/process/download`.

#### Historial Web

**Endpoint:** `GET /logs/web?limit=50`

Solo jobs creados desde el endpoint `/extract` (interfaz web).

#### Historial de Errores

**Endpoint:** `GET /logs/errors?limit=50`

Solo jobs con `status: failed`.

#### Estadísticas de Logs

**Endpoint:** `GET /logs/stats`

**Respuesta:**
```json
{
  "total": 150,
  "pending": 2,
  "processing": 3,
  "completed": 140,
  "failed": 5,
  "api_total": 80,
  "web_total": 70
}
```

---

## Casos de Uso

### 1. Obtener link de audio (simple)

**Escenario:** Quieres el link permanente al archivo de audio.

**Usar:** `POST /process`

```bash
curl -X POST "https://videoconverter-api.8r3zyw.easypanel.host/api/process" \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://www.youtube.com/watch?v=VIDEO_ID", "format": "mp3", "quality": "192"}'
```

**Resultado:** JSON con `audio_url` que puedes guardar o compartir.

---

### 2. Descargar archivo directamente

**Escenario:** Necesitas el archivo binario para guardarlo, enviarlo por email, subirlo a otro servicio, etc.

**Usar:** `POST /process/download`

```bash
curl -X POST "https://videoconverter-api.8r3zyw.easypanel.host/api/process/download" \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://www.youtube.com/watch?v=VIDEO_ID", "format": "mp3", "quality": "320"}' \
  --output mi_audio.mp3
```

**Resultado:** Archivo de audio descargado localmente.

---

### 3. Verificar video antes de procesar

**Escenario:** Quieres saber la duración y título antes de iniciar la extracción.

**Usar:** `GET /info`

```bash
curl "https://videoconverter-api.8r3zyw.easypanel.host/api/info?url=https://www.youtube.com/watch?v=VIDEO_ID"
```

**Resultado:** Información del video sin descargarlo.

---

### 4. Procesamiento no bloqueante (async)

**Escenario:** Tu aplicación no puede esperar varios minutos por la respuesta.

**Usar:** `POST /extract` + polling con `GET /jobs/{job_id}`

```bash
# Paso 1: Iniciar
JOB_ID=$(curl -s -X POST "https://videoconverter-api.8r3zyw.easypanel.host/api/extract" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID", "format": "mp3", "quality": "192"}' | jq -r '.job_id')

echo "Job ID: $JOB_ID"

# Paso 2: Polling hasta completar
while true; do
  STATUS=$(curl -s "https://videoconverter-api.8r3zyw.easypanel.host/api/jobs/$JOB_ID" | jq -r '.status')
  echo "Estado: $STATUS"
  
  if [ "$STATUS" = "completed" ]; then
    curl -s "https://videoconverter-api.8r3zyw.easypanel.host/api/jobs/$JOB_ID" | jq '.result.audio_url'
    break
  elif [ "$STATUS" = "failed" ]; then
    echo "Error!"
    break
  fi
  
  sleep 2
done
```

---

### 5. Monitoreo y estadísticas

**Escenario:** Quieres ver el uso de la API.

```bash
# Estadísticas generales
curl "https://videoconverter-api.8r3zyw.easypanel.host/api/logs/stats"

# Ver errores recientes
curl "https://videoconverter-api.8r3zyw.easypanel.host/api/logs/errors?limit=10"

# Ver últimos jobs exitosos de API
curl "https://videoconverter-api.8r3zyw.easypanel.host/api/logs/api?limit=10"
```

---

## Códigos de Error

| Código | Descripción | Solución |
|--------|-------------|----------|
| `SUPABASE_NOT_CONFIGURED` | Storage no configurado | Verificar variables de entorno |
| `VIDEO_TOO_LONG` | Video excede duración máxima | Usar video más corto |
| `VIDEO_NOT_FOUND` | URL inválida o video privado | Verificar URL y disponibilidad |
| `DOWNLOAD_ERROR` | Error al descargar | Reintentar o verificar URL |
| `EXTRACTION_ERROR` | Error al extraer audio | Verificar formato soportado |
| `UPLOAD_ERROR` | Error al subir a storage | Reintentar |
| `INTERNAL_ERROR` | Error interno | Contactar soporte |

---

## Ejemplos de Integración

### n8n - Obtener Link

```json
{
  "method": "POST",
  "url": "https://videoconverter-api.8r3zyw.easypanel.host/api/process",
  "sendBody": true,
  "specifyBody": "json",
  "jsonBody": "{\"video_url\": \"{{ $json.youtube_url }}\", \"format\": \"mp3\", \"quality\": \"192\"}",
  "options": {
    "timeout": 300000
  }
}
```

### n8n - Descargar Archivo

```json
{
  "method": "POST",
  "url": "https://videoconverter-api.8r3zyw.easypanel.host/api/process/download",
  "sendBody": true,
  "specifyBody": "json",
  "jsonBody": "{\"video_url\": \"{{ $json.youtube_url }}\", \"format\": \"mp3\", \"quality\": \"192\"}",
  "options": {
    "response": {
      "response": {
        "responseFormat": "file"
      }
    },
    "timeout": 300000
  }
}
```

### Python

```python
import requests

# Obtener link
response = requests.post(
    "https://videoconverter-api.8r3zyw.easypanel.host/api/process",
    json={
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "format": "mp3",
        "quality": "192"
    },
    timeout=300
)
data = response.json()
print(f"Audio URL: {data['audio_url']}")

# Descargar archivo
response = requests.post(
    "https://videoconverter-api.8r3zyw.easypanel.host/api/process/download",
    json={
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "format": "mp3",
        "quality": "320"
    },
    timeout=300
)
with open("audio.mp3", "wb") as f:
    f.write(response.content)
print(f"Descargado: {response.headers.get('X-File-Size')}")
```

### JavaScript/Node.js

```javascript
// Obtener link
const response = await fetch(
  "https://videoconverter-api.8r3zyw.easypanel.host/api/process",
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      video_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      format: "mp3",
      quality: "192"
    })
  }
);
const data = await response.json();
console.log(`Audio URL: ${data.audio_url}`);

// Descargar archivo
const downloadResponse = await fetch(
  "https://videoconverter-api.8r3zyw.easypanel.host/api/process/download",
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      video_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      format: "mp3",
      quality: "320"
    })
  }
);
const audioBuffer = await downloadResponse.arrayBuffer();
// Guardar o procesar el buffer...
```

---

## Límites y Consideraciones

- **Timeout:** Los endpoints síncronos pueden tardar varios minutos para videos largos. Usar timeout de 300 segundos mínimo.
- **Duración:** Configurable via `MAX_DURATION_MINUTES` (default: sin límite).
- **Formatos soportados:** YouTube y Vimeo.
- **Almacenamiento:** Los archivos se guardan en Supabase Storage indefinidamente.

---

## Soporte

- **Frontend:** https://videoconverter-video-to-audio.8r3zyw.easypanel.host
- **GitHub:** https://github.com/OscarAlejs/video-to-audio
