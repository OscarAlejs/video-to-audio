# 🎵 Video to Audio

Aplicación full-stack para extraer audio de videos de YouTube y Vimeo, almacenándolos en Supabase Storage.

![Stack](https://img.shields.io/badge/Stack-FastAPI%20%2B%20React-blueviolet)
![Python](https://img.shields.io/badge/Python-3.11+-blue)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue)

## ✨ Características

- 🎥 Soporta YouTube y Vimeo
- 🎧 Múltiples formatos: MP3, M4A, WAV, OPUS
- 📊 Calidades: 128-320 kbps
- ☁️ Almacenamiento en Supabase Storage
- 📱 Interfaz responsive y moderna
- ⚡ Procesamiento asíncrono con progreso en tiempo real
- 🐳 Docker ready

## 🏗️ Arquitectura

```
video-to-audio/
├── backend/                 # FastAPI API
│   ├── app/
│   │   ├── services/       # Lógica de negocio
│   │   ├── config.py       # Configuración
│   │   ├── models.py       # Modelos Pydantic
│   │   ├── routes.py       # Endpoints API
│   │   └── main.py         # Entry point
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/               # React + Vite
│   ├── src/
│   │   ├── components/    # Componentes React
│   │   ├── hooks/         # Custom hooks
│   │   ├── services/      # API client
│   │   ├── types/         # TypeScript types
│   │   └── App.tsx        # Componente principal
│   ├── Dockerfile
│   └── package.json
│
├── docker-compose.yml      # Orquestación
└── .env.example           # Variables de entorno
```

## 🚀 Quick Start

### 1. Clonar y configurar

```bash
git clone <repo>
cd video-to-audio

# Copiar variables de entorno
cp .env.example .env
```

### 2. Configurar Supabase

1. Crea un proyecto en [supabase.com](https://supabase.com)
2. Ve a **Storage** y crea un bucket llamado `audio-files`
3. Configura el bucket como **público** (para URLs públicas)
4. Copia tu `Project URL` y `anon key` desde **Settings > API**
5. Edita `.env` con tus credenciales

### 3. Ejecutar con Docker

```bash
# Producción
docker-compose up -d

# Ver logs
docker-compose logs -f
```

La aplicación estará en:
- **Frontend**: http://localhost
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### 4. Desarrollo local (sin Docker)

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Necesitas ffmpeg instalado
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## 📡 API Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/health` | Estado del servicio |
| GET | `/api/info?url=...` | Info del video sin descargar |
| POST | `/api/extract` | Iniciar extracción (async) |
| GET | `/api/jobs/{id}` | Estado de un job |
| GET | `/api/jobs` | Listar todos los jobs |
| GET | `/api/jobs/stats` | Estadísticas |

### Ejemplo de uso

```bash
# Obtener info del video
curl "http://localhost:8000/api/info?url=https://youtube.com/watch?v=dQw4w9WgXcQ"

# Iniciar extracción
curl -X POST http://localhost:8000/api/extract \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
    "format": "mp3",
    "quality": "192"
  }'

# Consultar estado
curl http://localhost:8000/api/jobs/{job_id}
```

## ⚙️ Configuración

| Variable | Descripción | Default |
|----------|-------------|---------|
| `SUPABASE_URL` | URL del proyecto Supabase | (requerido) |
| `SUPABASE_KEY` | API Key (anon o service) | (requerido) |
| `SUPABASE_BUCKET` | Nombre del bucket | `audio-files` |
| `MAX_DURATION_MINUTES` | Duración máxima de video | `60` |

## 🛡️ Configuración de Supabase Storage

En el SQL Editor de Supabase:

```sql
-- Crear bucket
INSERT INTO storage.buckets (id, name, public)
VALUES ('audio-files', 'audio-files', true);

-- Política de lectura pública
CREATE POLICY "Public read access"
ON storage.objects FOR SELECT
USING (bucket_id = 'audio-files');

-- Política de escritura (para el servicio)
CREATE POLICY "Service write access"
ON storage.objects FOR INSERT
WITH CHECK (bucket_id = 'audio-files');
```

## 🔌 Integración con n8n

```json
{
  "nodes": [
    {
      "name": "Extract Audio",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "POST",
        "url": "http://backend:8000/api/extract",
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            { "name": "url", "value": "={{ $json.video_url }}" },
            { "name": "format", "value": "mp3" },
            { "name": "quality", "value": "192" }
          ]
        }
      }
    }
  ]
}
```

## 🐛 Troubleshooting

**"Supabase no configurado"**
→ Verifica que `SUPABASE_URL` y `SUPABASE_KEY` estén en `.env`

**"Video muy largo"**
→ Aumenta `MAX_DURATION_MINUTES` o usa videos más cortos

**Error de ffmpeg**
→ Docker ya incluye ffmpeg. Si corres sin Docker, instala:
- Ubuntu: `sudo apt install ffmpeg`
- macOS: `brew install ffmpeg`
- Windows: `choco install ffmpeg`

**CORS errors**
→ Verifica que la URL del frontend esté en `CORS_ORIGINS`

## 📝 Licencia

MIT

---

Made with ❤️
