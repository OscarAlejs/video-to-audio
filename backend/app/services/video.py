@ -1,67 +1,58 @@
"""
Servicio de descarga y extracción de audio
"""
import uuid
import requests
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

import yt_dlp

from ..config import get_settings
from ..models import AudioFormat, AudioQuality, VideoInfo


TEMP_DIR = Path("/tmp/video-to-audio")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

COOKIES_FILE = Path("/app/cookies.txt")


def format_duration(seconds: int) -> str:
    if not seconds:
        return "0:00"
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_file_size(bytes_size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def get_base_ydl_opts() -> dict:
    """Opciones base - estabilidad sobre velocidad"""
    opts = {
        "quiet": True,
        "no_warnings": True,
        # === ESTABILIDAD ===
        "concurrent_fragment_downloads": 1,  # Sin concurrencia (evita ConnectionTerminated)
        "retries": 10,
        "fragment_retries": 10,
        # === FIX HTTP/2 ===
        "legacy_server_connect": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        "extractor_args": {
            "youtube": {"player_client": "web"},
            "vimeo": {"http_version": "1.1"},
        },
    }
@ -74,9 +65,11 @@ def is_direct_file_url(url: str) -> bool:
    """Detecta si es una URL directa de archivo"""
    video_extensions = [".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".wmv", ".m4v", ".mpeg", ".mpg", ".3gp"]
    
    # Extensión en URL
    if any(url.lower().endswith(ext) for ext in video_extensions):
        return True
    
    # URLs de Supabase Storage
    if "supabase.co/storage" in url.lower():
        return True
    
@ -84,7 +77,9 @@ def is_direct_file_url(url: str) -> bool:


def download_direct_file(url: str, output_path: Path) -> Path:
    """
    Descarga un archivo directo desde una URL
    """
    print(f"📥 Descargando archivo directo: {url}")
    
    try:
@ -95,14 +90,14 @@ def download_direct_file(url: str, output_path: Path) -> Path:
        downloaded = 0
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        if progress % 10 < 1:  # Log cada 10%
                            print(f"   📥 Descarga: {progress:.0f}%")
        
        print(f"✅ Descarga completada: {output_path.name}")
@ -138,18 +133,20 @@ def get_video_duration_from_file(file_path: Path) -> Optional[int]:
def get_video_info(url: str) -> VideoInfo:
    """Obtiene información del video (YouTube/Vimeo o archivo directo)"""
    
    # Si es archivo directo, obtener info básica
    if is_direct_file_url(url):
        filename = urlparse(url).path.split('/')[-1]
        return VideoInfo(
            id="direct_file",
            title=filename,
            duration_seconds=0,  # Se obtendrá después de descargar
            duration_formatted="Desconocida",
            thumbnail=None,
            source="direct_url",
            channel=None,
        )
    
    # YouTube/Vimeo (código existente)
    ydl_opts = {
        **get_base_ydl_opts(),
        "extract_flat": False,
@ -179,10 +176,11 @@ def download_and_extract(
    settings = get_settings()
    unique_id = str(uuid.uuid4())[:8]
    
    # Detectar si es archivo directo
    if is_direct_file_url(url):
        print(f"🔗 Procesando URL directa: {url}")
        
        # Descargar archivo
        filename = urlparse(url).path.split('/')[-1] or f"video_{unique_id}.mp4"
        temp_video = TEMP_DIR / f"{unique_id}_{filename}"
        
@ -194,8 +192,10 @@ def download_and_extract(
        if progress_callback:
            progress_callback("downloading", 50)
        
        # Obtener duración del archivo descargado
        duration = get_video_duration_from_file(temp_video)
        
        # Validar duración
        if duration and duration > settings.max_duration_minutes * 60:
            cleanup_file(temp_video)
            raise ValueError(
@ -203,6 +203,7 @@ def download_and_extract(
                f"Máximo permitido: {settings.max_duration_minutes} min"
            )
        
        # Extraer audio usando función del módulo upload
        if progress_callback:
            progress_callback("extracting", 60)
        
@ -216,8 +217,10 @@ def download_and_extract(
        if progress_callback:
            progress_callback("extracting", 90)
        
        # Limpiar video temporal
        cleanup_file(temp_video)
        
        # Crear VideoInfo
        video_info = VideoInfo(
            id="direct_file",
            title=filename,
@ -230,7 +233,7 @@ def download_and_extract(
        
        return audio_file, video_info
    
    # YouTube/Vimeo (código existente)
    output_template = str(TEMP_DIR / f"{unique_id}_%(title).50s.%(ext)s")
    
    print(f"🎬 Descargando video de {url}")
@ -245,16 +248,12 @@ def download_and_extract(
                    percent = int(d.get("downloaded_bytes", 0) / d["total_bytes_estimate"] * 50)
                progress_callback("downloading", percent)
            
            # Log de progreso de descarga
            if d.get("total_bytes"):
                mb_downloaded = d.get("downloaded_bytes", 0) / (1024 * 1024)
                mb_total = d["total_bytes"] / (1024 * 1024)
                percent = int(d.get("downloaded_bytes", 0) / d["total_bytes"] * 100)
                print(f"   📥 Descarga: {mb_downloaded:.1f}/{mb_total:.1f} MB ({percent}%)")
        elif d["status"] == "finished":
            print(f"   ✅ Descarga completada")
            if progress_callback:
@ -275,8 +274,8 @@ def download_and_extract(
        "outtmpl": output_template,
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
        # === FORMATO ===
        "format": "worstvideo+bestaudio/bestaudio/worst",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": output_format.value,
