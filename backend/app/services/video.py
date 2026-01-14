"""
Servicio para descarga y procesamiento de videos/audio con yt-dlp.
"""

import logging
import os
import re
import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple

import yt_dlp

from app.config import AUDIO_DIR, COOKIES_FILE, MAX_VIDEO_DURATION_MINUTES, TEMP_DIR

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    """
    Elimina caracteres inválidos de un nombre de archivo.
    """
    # Eliminar caracteres no permitidos en nombres de archivo
    filename = re.sub(r'[<>:"/\\|?*]', "", filename)
    # Reemplazar espacios múltiples con uno solo
    filename = re.sub(r"\s+", " ", filename)
    # Limitar longitud
    max_length = 200
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        filename = name[: max_length - len(ext)] + ext
    return filename.strip()


def get_base_ydl_opts() -> dict:
    """Opciones optimizadas contra errores de conexión HTTP/2"""
    opts = {
        "quiet": True,
        "no_warnings": True,
        # === ESTABILIDAD MÁXIMA ===
        "concurrent_fragment_downloads": 1,  # Sin concurrencia (evita ConnectionTerminated)
        "retries": 25,              # Aumentado de 10 a 25
        "fragment_retries": 25,     # Aumentado de 10 a 25
        "file_access_retries": 10,  # Nuevo
        "extractor_retries": 5,     # Nuevo
        # === FIX HTTP/2 - FORZAR HTTP/1.1 ===
        "legacy_server_connect": True,
        "socket_timeout": 120,      # 2 minutos timeout
        "http_chunk_size": 5242880, # 5MB chunks (más pequeños = más estables)
        # === HEADERS OPTIMIZADOS ===
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-us,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",  # Sin "br" (Brotli requiere HTTP/2)
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        },
        # === EXTRACTORS ===
        "extractor_args": {
            "youtube": {
                "player_client": "web",
                "player_skip": ["configs"],  # Skip parsing extra que puede fallar
            },
            "vimeo": {"http_version": "1.1"},
        },
    }
    if COOKIES_FILE.exists():
        opts["cookiefile"] = str(COOKIES_FILE)
    return opts


def get_video_info(url: str) -> Dict:
    """
    Obtiene información del video sin descargarlo.
    
    Args:
        url: URL del video
        
    Returns:
        Dict con información del video
        
    Raises:
        Exception: Si hay error al obtener info
    """
    ydl_opts = get_base_ydl_opts()
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Obteniendo información de: {url}")
            info = ydl.extract_info(url, download=False)
            
            # Validar duración
            duration_seconds = info.get("duration", 0)
            max_duration_seconds = MAX_VIDEO_DURATION_MINUTES * 60
            
            if duration_seconds > max_duration_seconds:
                raise ValueError(
                    f"El video dura {duration_seconds//60} minutos. "
                    f"Máximo permitido: {MAX_VIDEO_DURATION_MINUTES} minutos"
                )
            
            return {
                "title": info.get("title", "Sin título"),
                "duration": duration_seconds,
                "thumbnail": info.get("thumbnail"),
                "uploader": info.get("uploader", "Desconocido"),
                "webpage_url": info.get("webpage_url", url),
            }
            
    except Exception as e:
        logger.error(f"Error al obtener info del video: {e}")
        raise


def download_audio(
    url: str, format_preference: str = "mp3", bitrate: str = "192"
) -> Tuple[Path, Dict]:
    """
    Descarga el audio de un video en el formato especificado.
    
    Args:
        url: URL del video
        format_preference: Formato de audio deseado (mp3, m4a, opus)
        bitrate: Bitrate del audio (64, 128, 192, 256, 320)
        
    Returns:
        Tuple con (ruta del archivo, info del video)
        
    Raises:
        Exception: Si hay error en la descarga
    """
    # Validar formato
    valid_formats = ["mp3", "m4a", "opus"]
    if format_preference not in valid_formats:
        format_preference = "mp3"
    
    # Validar bitrate
    valid_bitrates = ["64", "128", "192", "256", "320"]
    if bitrate not in valid_bitrates:
        bitrate = "192"
    
    # Crear directorio temporal si no existe
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Obtener info primero
    info = get_video_info(url)
    
    # Sanitizar título para nombre de archivo
    safe_title = sanitize_filename(info["title"])
    
    # Configurar opciones de descarga
    ydl_opts = get_base_ydl_opts()
    ydl_opts.update(
        {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": format_preference,
                    "preferredquality": bitrate,
                }
            ],
            "outtmpl": str(TEMP_DIR / f"{safe_title}.%(ext)s"),
            "keepvideo": False,
        }
    )
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Descargando audio de: {url}")
            ydl.download([url])
            
            # Buscar archivo descargado
            expected_file = TEMP_DIR / f"{safe_title}.{format_preference}"
            
            if not expected_file.exists():
                # Buscar cualquier archivo con el título
                matching_files = list(TEMP_DIR.glob(f"{safe_title}.*"))
                if matching_files:
                    expected_file = matching_files[0]
                else:
                    raise FileNotFoundError(
                        f"No se encontró el archivo descargado: {expected_file}"
                    )
            
            # Mover a directorio final
            AUDIO_DIR.mkdir(parents=True, exist_ok=True)
            final_path = AUDIO_DIR / expected_file.name
            
            # Si ya existe, agregar sufijo numérico
            counter = 1
            while final_path.exists():
                stem = expected_file.stem
                suffix = expected_file.suffix
                final_path = AUDIO_DIR / f"{stem}_{counter}{suffix}"
                counter += 1
            
            shutil.move(str(expected_file), str(final_path))
            logger.info(f"Audio guardado en: {final_path}")
            
            return final_path, info
            
    except Exception as e:
        logger.error(f"Error al descargar audio: {e}")
        # Limpiar archivos temporales
        for f in TEMP_DIR.glob(f"{safe_title}.*"):
            try:
                f.unlink()
            except Exception:
                pass
        raise


def cleanup_temp_files() -> int:
    """
    Limpia archivos temporales antiguos (más de 1 hora).
    
    Returns:
        Número de archivos eliminados
    """
    import time
    
    deleted = 0
    current_time = time.time()
    max_age = 3600  # 1 hora en segundos
    
    try:
        for file_path in TEMP_DIR.glob("*"):
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age:
                    file_path.unlink()
                    deleted += 1
                    logger.info(f"Archivo temporal eliminado: {file_path.name}")
    except Exception as e:
        logger.error(f"Error al limpiar archivos temporales: {e}")
    
    return deleted
