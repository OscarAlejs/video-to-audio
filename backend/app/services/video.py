"""
Servicio de descarga y extracción de audio
"""
import uuid
import subprocess
import asyncio
from pathlib import Path
from typing import Callable, Optional

import yt_dlp
from pybalt import Cobalt

from ..config import get_settings
from ..models import AudioFormat, AudioQuality, VideoInfo


TEMP_DIR = Path("/tmp/video-to-audio")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Cookies de YouTube
COOKIES_FILE = Path("/app/cookies.txt")


def format_duration(seconds: int) -> str:
    """Formatea segundos a formato legible"""
    if not seconds:
        return "0:00"
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_file_size(bytes_size: int) -> str:
    """Formatea bytes a formato legible"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def is_youtube_url(url: str) -> bool:
    """Detecta si es una URL de YouTube"""
    return any(x in url.lower() for x in ['youtube.com', 'youtu.be'])


def get_base_ydl_opts() -> dict:
    """Opciones base para yt-dlp"""
    opts = {
        "quiet": True,
        "no_warnings": True,
    }
    if COOKIES_FILE.exists():
        opts["cookiefile"] = str(COOKIES_FILE)
    return opts


def get_video_info_from_url(url: str) -> VideoInfo:
    """Obtiene info básica de YouTube desde la URL"""
    import re
    
    video_id = None
    patterns = [
        r'(?:v=|/)([\w-]{11})',
        r'youtu\.be/([\w-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            break
    
    if not video_id:
        video_id = "unknown"
    
    return VideoInfo(
        id=video_id,
        title="YouTube Video",
        duration_seconds=0,
        duration_formatted="--:--",
        thumbnail=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        source="youtube",
        channel=None,
    )


def get_video_info(url: str) -> VideoInfo:
    """Obtiene información del video usando yt-dlp"""
    ydl_opts = {
        **get_base_ydl_opts(),
        "extract_flat": False,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
        duration = info.get("duration", 0) or 0
        
        return VideoInfo(
            id=info.get("id", "unknown"),
            title=info.get("title", "Sin título"),
            duration_seconds=duration,
            duration_formatted=format_duration(duration),
            thumbnail=info.get("thumbnail"),
            source=info.get("extractor", "unknown"),
            channel=info.get("channel") or info.get("uploader"),
        )


def download_with_cobalt(
    url: str,
    output_format: AudioFormat,
    quality: AudioQuality,
    unique_id: str,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> Path:
    """Descarga audio usando pybalt (Cobalt)"""
    
    if progress_callback:
        progress_callback("downloading", 10)
    
    # Crear cliente Cobalt
    cobalt = Cobalt(url)
    cobalt.audio_only()
    cobalt.audio_format("mp3")
    
    if progress_callback:
        progress_callback("downloading", 30)
    
    # Descargar
    output_path = str(TEMP_DIR)
    
    # Ejecutar descarga de forma síncrona
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(cobalt.download(output_path))
    finally:
        loop.close()
    
    if progress_callback:
        progress_callback("extracting", 60)
    
    # Buscar archivo descargado
    downloaded_file = None
    for file in TEMP_DIR.glob("*"):
        if file.is_file() and file.stat().st_mtime > 0:
            # Verificar si es un archivo reciente
            import time
            if time.time() - file.stat().st_mtime < 60:
                downloaded_file = file
                break
    
    if not downloaded_file:
        raise FileNotFoundError("No se encontró el archivo descargado")
    
    # Renombrar/convertir si es necesario
    final_file = TEMP_DIR / f"{unique_id}_cobalt.{output_format.value}"
    
    if output_format.value != "mp3" or downloaded_file.suffix != f".{output_format.value}":
        subprocess.run([
            "ffmpeg", "-i", str(downloaded_file),
            "-b:a", f"{quality.value}k",
            "-y", str(final_file)
        ], capture_output=True, check=True)
        downloaded_file.unlink()
    else:
        downloaded_file.rename(final_file)
    
    if progress_callback:
        progress_callback("extracting", 90)
    
    return final_file


def download_with_ytdlp(
    url: str,
    output_format: AudioFormat,
    quality: AudioQuality,
    unique_id: str,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> Path:
    """Descarga audio usando yt-dlp (para Vimeo y otros)"""
    
    output_template = str(TEMP_DIR / f"{unique_id}_%(title).50s.%(ext)s")
    
    def progress_hook(d):
        if d["status"] == "downloading":
            if progress_callback:
                percent = 0
                if d.get("total_bytes"):
                    percent = int(d.get("downloaded_bytes", 0) / d["total_bytes"] * 50)
                elif d.get("total_bytes_estimate"):
                    percent = int(d.get("downloaded_bytes", 0) / d["total_bytes_estimate"] * 50)
                progress_callback("downloading", percent)
        elif d["status"] == "finished":
            if progress_callback:
                progress_callback("extracting", 60)
    
    def postprocessor_hook(d):
        if d["status"] == "started":
            if progress_callback:
                progress_callback("extracting", 70)
        elif d["status"] == "finished":
            if progress_callback:
                progress_callback("extracting", 90)
    
    ydl_opts = {
        **get_base_ydl_opts(),
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": output_format.value,
            "preferredquality": quality.value,
        }],
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)
    
    for file in TEMP_DIR.glob(f"{unique_id}_*"):
        if file.suffix == f".{output_format.value}":
            return file
    
    raise FileNotFoundError("No se encontró el archivo de audio")


def download_and_extract(
    url: str,
    output_format: AudioFormat = AudioFormat.MP3,
    quality: AudioQuality = AudioQuality.MEDIUM,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> tuple[Path, VideoInfo]:
    """
    Descarga video y extrae audio
    Usa Cobalt para YouTube, yt-dlp para otros
    """
    settings = get_settings()
    unique_id = str(uuid.uuid4())[:8]
    
    if is_youtube_url(url):
        # Para YouTube, usar Cobalt (pybalt)
        video_info = get_video_info_from_url(url)
        audio_file = download_with_cobalt(url, output_format, quality, unique_id, progress_callback)
    else:
        # Para otros sitios, usar yt-dlp
        video_info = get_video_info(url)
        
        if video_info.duration_seconds > settings.max_duration_minutes * 60:
            raise ValueError(
                f"Video muy largo ({video_info.duration_seconds // 60} min). "
                f"Máximo permitido: {settings.max_duration_minutes} min"
            )
        
        audio_file = download_with_ytdlp(url, output_format, quality, unique_id, progress_callback)
    
    return audio_file, video_info


def cleanup_file(file_path: Path) -> None:
    """Elimina archivo temporal"""
    try:
        if file_path and file_path.exists():
            file_path.unlink()
    except Exception:
        pass


def cleanup_old_files(max_age_hours: int = 1) -> int:
    """Limpia archivos temporales antiguos"""
    import time
    
    count = 0
    now = time.time()
    max_age_seconds = max_age_hours * 3600
    
    for file in TEMP_DIR.glob("*"):
        if now - file.stat().st_mtime > max_age_seconds:
            cleanup_file(file)
            count += 1
    
    return count
