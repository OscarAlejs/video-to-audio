"""
Servicio para descarga y procesamiento de videos/audio usando yt-dlp.
Diseñado para manejar múltiples plataformas y formatos.
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional, Dict, Any

import yt_dlp

from ..config import DOWNLOAD_DIR, COOKIES_FILE

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTES DE CONFIGURACIÓN
# ============================================================================

MAX_FILE_SIZE_MB = 100
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Formatos de audio preferidos en orden de calidad
PREFERRED_AUDIO_FORMATS = ["m4a", "mp3", "opus", "webm"]

# Patrones de URL soportados
SUPPORTED_PLATFORMS = {
    "youtube": r"(?:youtube\.com|youtu\.be)",
    "vimeo": r"vimeo\.com",
    "soundcloud": r"soundcloud\.com",
}


# ============================================================================
# YT-DLP OPTIONS BUILDERS
# ============================================================================

def get_base_ydl_opts() -> dict:
    """Opciones optimizadas contra errores de conexión HTTP/2"""
    opts = {
        "quiet": True,
        "no_warnings": True,
        # === ESTABILIDAD MÁXIMA ===
        "concurrent_fragment_downloads": 1,  # Sin concurrencia
        "retries": 25,              # 10 → 25 (más reintentos)
        "fragment_retries": 25,     # 10 → 25 (más reintentos por fragmento)
        "file_access_retries": 10,  # Reintentos de acceso a archivo
        "extractor_retries": 5,     # Reintentos de extractor
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


def get_info_opts() -> dict:
    """Opciones específicas para extraer información"""
    opts = get_base_ydl_opts()
    opts.update({
        "skip_download": True,
        "ignoreerrors": False,
    })
    return opts


def get_download_opts(output_path: Path, format_spec: str = "bestaudio") -> dict:
    """Opciones específicas para descarga"""
    opts = get_base_ydl_opts()
    opts.update({
        "format": format_spec,
        "outtmpl": str(output_path),
        "postprocessors": [],
    })
    return opts


# ============================================================================
# VALIDACIÓN Y UTILIDADES
# ============================================================================

def validate_url(url: str) -> bool:
    """Valida si la URL es de una plataforma soportada"""
    return any(re.search(pattern, url) for pattern in SUPPORTED_PLATFORMS.values())


def sanitize_filename(filename: str) -> str:
    """Sanitiza nombre de archivo eliminando caracteres no válidos"""
    # Reemplazar caracteres problemáticos
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")
    
    # Limitar longitud (Windows tiene límite de 255 caracteres)
    max_length = 200
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        filename = name[:max_length - len(ext)] + ext
    
    return filename.strip()


def estimate_file_size(info: Dict[str, Any]) -> Optional[int]:
    """Estima el tamaño del archivo en bytes"""
    # Intentar obtener tamaño directo
    if "filesize" in info and info["filesize"]:
        return info["filesize"]
    
    if "filesize_approx" in info and info["filesize_approx"]:
        return info["filesize_approx"]
    
    # Calcular basado en bitrate y duración
    duration = info.get("duration")
    bitrate = info.get("abr") or info.get("tbr")
    
    if duration and bitrate:
        # bitrate en kbps, duration en segundos
        estimated_size = (bitrate * 1000 * duration) / 8
        return int(estimated_size)
    
    return None


# ============================================================================
# FUNCIONES PRINCIPALES
# ============================================================================

def get_video_info(url: str) -> Dict[str, Any]:
    """
    Extrae información del video sin descargarlo.
    
    Args:
        url: URL del video
        
    Returns:
        Dict con información del video
        
    Raises:
        ValueError: Si la URL no es válida
        yt_dlp.utils.DownloadError: Si hay error al extraer información
    """
    if not validate_url(url):
        raise ValueError(f"URL no soportada: {url}")
    
    logger.info(f"Extrayendo información de: {url}")
    
    ydl_opts = get_info_opts()
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Extraer información relevante
            result = {
                "title": info.get("title", "Unknown"),
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", "Unknown"),
                "thumbnail": info.get("thumbnail"),
                "description": info.get("description", ""),
                "formats_available": len(info.get("formats", [])),
            }
            
            # Estimar tamaño
            estimated_size = estimate_file_size(info)
            if estimated_size:
                result["estimated_size_mb"] = round(estimated_size / (1024 * 1024), 2)
            
            logger.info(f"Información extraída: {result['title']}")
            return result
            
    except Exception as e:
        logger.error(f"Error extrayendo información: {str(e)}")
        raise


def download_audio(
    url: str,
    output_filename: Optional[str] = None,
    preferred_format: str = "m4a"
) -> Path:
    """
    Descarga solo el audio de un video.
    
    Args:
        url: URL del video
        output_filename: Nombre personalizado para el archivo (sin extensión)
        preferred_format: Formato de audio preferido
        
    Returns:
        Path al archivo descargado
        
    Raises:
        ValueError: Si la URL no es válida o el archivo excede el tamaño máximo
        yt_dlp.utils.DownloadError: Si hay error en la descarga
    """
    if not validate_url(url):
        raise ValueError(f"URL no soportada: {url}")
    
    logger.info(f"Iniciando descarga de audio desde: {url}")
    
    # Verificar tamaño estimado
    info = get_video_info(url)
    estimated_size = info.get("estimated_size_mb")
    if estimated_size and estimated_size > MAX_FILE_SIZE_MB:
        raise ValueError(
            f"Archivo muy grande ({estimated_size:.2f}MB). "
            f"Máximo permitido: {MAX_FILE_SIZE_MB}MB"
        )
    
    # Preparar nombre de archivo
    if not output_filename:
        output_filename = sanitize_filename(info["title"])
    else:
        output_filename = sanitize_filename(output_filename)
    
    # Path de salida (sin extensión, yt-dlp la añadirá)
    output_path = DOWNLOAD_DIR / output_filename
    
    # Configurar formato de audio
    format_spec = f"bestaudio[ext={preferred_format}]/bestaudio"
    
    ydl_opts = get_download_opts(output_path, format_spec)
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Descargando: {info['title']}")
            ydl.download([url])
            
            # Buscar archivo descargado
            downloaded_files = list(DOWNLOAD_DIR.glob(f"{output_filename}.*"))
            
            if not downloaded_files:
                raise FileNotFoundError("No se encontró el archivo descargado")
            
            downloaded_file = downloaded_files[0]
            
            # Verificar tamaño real
            file_size_mb = downloaded_file.stat().st_size / (1024 * 1024)
            if file_size_mb > MAX_FILE_SIZE_MB:
                downloaded_file.unlink()  # Eliminar archivo
                raise ValueError(
                    f"Archivo descargado muy grande ({file_size_mb:.2f}MB). "
                    f"Máximo: {MAX_FILE_SIZE_MB}MB"
                )
            
            logger.info(
                f"Descarga completada: {downloaded_file.name} "
                f"({file_size_mb:.2f}MB)"
            )
            return downloaded_file
            
    except Exception as e:
        logger.error(f"Error en descarga: {str(e)}")
        raise


def cleanup_old_files(max_age_hours: int = 24) -> int:
    """
    Limpia archivos antiguos del directorio de descargas.
    
    Args:
        max_age_hours: Edad máxima en horas
        
    Returns:
        Número de archivos eliminados
    """
    import time
    
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    deleted_count = 0
    
    for file_path in DOWNLOAD_DIR.glob("*"):
        if file_path.is_file():
            file_age = current_time - file_path.stat().st_mtime
            if file_age > max_age_seconds:
                try:
                    file_path.unlink()
                    deleted_count += 1
                    logger.info(f"Archivo eliminado: {file_path.name}")
                except Exception as e:
                    logger.error(f"Error eliminando {file_path.name}: {str(e)}")
    
    if deleted_count > 0:
        logger.info(f"Limpieza completada: {deleted_count} archivos eliminados")
    
    return deleted_count
