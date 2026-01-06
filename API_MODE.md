# 🔌 API Mode - Video to Audio

## Endpoint Síncrono

El endpoint `/api/process` procesa videos de forma **síncrona** - espera hasta completar todo el proceso y devuelve el resultado directamente.

### POST /api/process

**Ideal para:** n8n, Make, Zapier, scripts, integraciones directas.

#### Request

```bash
curl -X POST http://localhost:8000/api/process \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "format": "mp3",
    "quality": "192"
  }'
```

#### Parámetros

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `video_url` | string | (requerido) | URL de YouTube o Vimeo |
| `format` | string | `"mp3"` | Formato: `mp3`, `m4a`, `wav`, `opus` |
| `quality` | string | `"192"` | Bitrate: `128`, `192`, `256`, `320` |

#### Response (Éxito)

```json
{
  "status": "success",
  "audio_url": "https://xxx.supabase.co/storage/v1/object/public/audio-files/audio/20260103_120000_rick_astley_never_gonna_give_you_up.mp3",
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
  "file_size_formatted": "4.9 MB",
  "duration": 212,
  "duration_formatted": "3:32",
  "format": "mp3",
  "quality": "192",
  "processing_time": 45.23,
  "message": "Audio extraído exitosamente"
}
```

#### Response (Error)

```json
{
  "status": "error",
  "error_code": "VIDEO_TOO_LONG",
  "message": "Video muy largo (120 min). Máximo: 60 min",
  "video_info": {...},
  "processing_time": 2.5
}
```

#### Códigos de Error

| Código | HTTP | Descripción |
|--------|------|-------------|
| `SUPABASE_NOT_CONFIGURED` | 200 | Falta configurar Supabase |
| `VIDEO_TOO_LONG` | 200 | Video excede duración máxima |
| `VALIDATION_ERROR` | 200 | URL inválida o no soportada |
| `EXTRACTION_FAILED` | 200 | Error al extraer audio |
| `INTERNAL_ERROR` | 200 | Error interno del servidor |

---

## Alias: POST /api/process-video

Mismo endpoint, diferente nombre (para compatibilidad con documentación anterior).

---

## Ejemplo con n8n

### HTTP Request Node

```json
{
  "method": "POST",
  "url": "http://tu-servidor:8000/api/process",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "video_url": "={{ $json.video_url }}",
    "format": "mp3",
    "quality": "192"
  },
  "timeout": 600000
}
```

### Workflow Completo

```
[Trigger] → [HTTP Request /api/process] → [IF status=success] → [Usar audio_url]
                                                              ↓
                                                         [Manejar error]
```

---

## Ejemplo con Python

```python
import requests

response = requests.post(
    "http://localhost:8000/api/process",
    json={
        "video_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "format": "mp3",
        "quality": "192"
    },
    timeout=600  # 10 minutos
)

data = response.json()

if data["status"] == "success":
    print(f"Audio URL: {data['audio_url']}")
    print(f"Duración: {data['duration_formatted']}")
    print(f"Tamaño: {data['file_size_formatted']}")
else:
    print(f"Error: {data['message']}")
```

---

## Ejemplo con JavaScript/Node.js

```javascript
const response = await fetch('http://localhost:8000/api/process', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    video_url: 'https://youtube.com/watch?v=dQw4w9WgXcQ',
    format: 'mp3',
    quality: '192'
  })
});

const data = await response.json();

if (data.status === 'success') {
  console.log('Audio URL:', data.audio_url);
} else {
  console.error('Error:', data.message);
}
```

---

## Timeouts Recomendados

| Duración Video | Timeout Recomendado |
|----------------|---------------------|
| < 5 min | 2 minutos |
| 5-15 min | 5 minutos |
| 15-30 min | 10 minutos |
| 30-60 min | 15 minutos |

---

## Diferencia con /api/extract

| Endpoint | Tipo | Uso |
|----------|------|-----|
| `POST /api/extract` | Asíncrono | Frontend con polling |
| `POST /api/process` | Síncrono | APIs, n8n, scripts |

`/api/extract` retorna inmediatamente un `job_id` y hay que hacer polling a `/api/jobs/{job_id}`.

`/api/process` espera hasta terminar y retorna el resultado completo.
