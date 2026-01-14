import logging
import os
from pathlib import Path
from typing import Optional

import yt_dlp
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

# Directorio base para descargas
DOWNLOAD_BASE_DIR = Path(settings.DOWNLOAD_DIR)
DOWNLOAD_BASE_DIR.mkdir(parents=True, exist_ok=True)

# Archivo de cookies (si existe)
COOKIES_FILE = Path(__file__).parent.parent.parent / "cookies.txt"


class VideoService:
    """Servicio para manejo de descargas de video/audio con yt-dlp"""

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Limpia el nombre de archivo de caracteres no permitidos"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, "_")
        return filename

    @staticmethod
    def get_download_path(video_id: str) -> Path:
        """Retorna la ruta de descarga para un video específico"""
        video_dir = DOWNLOAD_BASE_DIR / video_id
        video_dir.mkdir(parents=True, exist_ok=True)
        return video_dir


def get_base_ydl_opts() -> dict:
    """Opciones base optimizadas para evitar ConnectionTerminated y errores HTTP/2"""
    opts = {
        "quiet": True,
        "no_warnings": True,
        
        # === FORZAR HTTP/1.1 (Evita ConnectionTerminated) ===
        "http_version": "1.1",  # Forzar HTTP/1.1 en lugar de HTTP/2
        
        # === ESTABILIDAD MÁXIMA ===
        "concurrent_fragment_downloads": 1,  # Sin concurrencia
        "retries": 15,  # Más reintentos
        "fragment_retries": 15,
        "file_access_retries": 10,
        "extractor_retries": 5,
        
        # === TIMEOUTS LARGOS ===
        "socket_timeout": 30,
        
        # === USER AGENT Y HEADERS ===
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-us,en;q=0.5",
            "Sec-Fetch-Mode": "navigate",
        },
        
        # === EXTRACTOR ARGS ===
        "extractor_args": {
            "youtube": {
                "player_client": ["web"],  # Usar solo cliente web
                "skip": ["hls", "dash"],  # Evitar formatos problemáticos
            }
        },
    }
    
    # Cookies si existen
    if COOKIES_FILE.exists():
        opts["cookiefile"] = str(COOKIES_FILE)
    
    return opts


def get_video_info(url: str) -> dict:
    """
    Obtiene información del video sin descargarlo
    
    Args:
        url: URL del video
        
    Returns:
        dict: Información del video (título, duración, formatos, etc.)
        
    Raises:
        HTTPException: Si hay error al obtener la información
    """
    try:
        ydl_opts = get_base_ydl_opts()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            return {
                "id": info.get("id"),
                "title": info.get("title"),
                "duration": info.get("duration"),
                "thumbnail": info.get("thumbnail"),
                "uploader": info.get("uploader"),
                "view_count": info.get("view_count"),
                "upload_date": info.get("upload_date"),
            }
            
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Error al obtener información del video: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo obtener información del video: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error inesperado al obtener información: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno al procesar el video: {str(e)}"
        )


def download_audio(
    url: str,
    video_id: str,
    format_id: Optional[str] = None,
    quality: str = "best"
) -> dict:
    """
    Descarga el audio de un video
    
    Args:
        url: URL del video
        video_id: ID único para identificar la descarga
        format_id: ID específico del formato a descargar
        quality: Calidad deseada ('best', 'worst', o bitrate específico)
        
    Returns:
        dict: Información de la descarga (ruta del archivo, metadata, etc.)
        
    Raises:
        HTTPException: Si hay error en la descarga
    """
    try:
        service = VideoService()
        download_path = service.get_download_path(video_id)
        
        # Configuración de yt-dlp para audio
        ydl_opts = get_base_ydl_opts()
        ydl_opts.update({
            "format": format_id if format_id else "bestaudio/best",
            "outtmpl": str(download_path / "%(title)s.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Construir ruta del archivo descargado
            filename = ydl.prepare_filename(info)
            audio_filename = Path(filename).stem + ".mp3"
            audio_path = download_path / audio_filename
            
            return {
                "video_id": video_id,
                "title": info.get("title"),
                "duration": info.get("duration"),
                "file_path": str(audio_path),
                "file_size": audio_path.stat().st_size if audio_path.exists() else 0,
            }
            
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Error al descargar audio: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo descargar el audio: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error inesperado al descargar audio: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno al procesar la descarga: {str(e)}"
        )


def download_video(
    url: str,
    video_id: str,
    format_id: Optional[str] = None,
    quality: str = "best"
) -> dict:
    """
    Descarga un video completo
    
    Args:
        url: URL del video
        video_id: ID único para identificar la descarga
        format_id: ID específico del formato a descargar
        quality: Calidad deseada ('best', 'worst', o resolución específica)
        
    Returns:
        dict: Información de la descarga (ruta del archivo, metadata, etc.)
        
    Raises:
        HTTPException: Si hay error en la descarga
    """
    try:
        service = VideoService()
        download_path = service.get_download_path(video_id)
        
        # Configuración de yt-dlp para video
        ydl_opts = get_base_ydl_opts()
        ydl_opts.update({
            "format": format_id if format_id else "bestvideo+bestaudio/best",
            "outtmpl": str(download_path / "%(title)s.%(ext)s"),
            "merge_output_format": "mp4",
        })
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Construir ruta del archivo descargado
            filename = ydl.prepare_filename(info)
            video_path = Path(filename)
            
            # Si se hizo merge, el archivo puede tener extensión .mp4
            if not video_path.exists():
                video_path = video_path.with_suffix(".mp4")
            
            return {
                "video_id": video_id,
                "title": info.get("title"),
                "duration": info.get("duration"),
                "file_path": str(video_path),
                "file_size": video_path.stat().st_size if video_path.exists() else 0,
                "resolution": f"{info.get('width')}x{info.get('height')}" if info.get('width') else None,
            }
            
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Error al descargar video: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo descargar el video: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error inesperado al descargar video: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno al procesar la descarga: {str(e)}"
        )
