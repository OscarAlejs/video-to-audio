"""
Servicio de descarga y extracción de audio
"""
import uuid
from pathlib import Path
from typing import Callable, Optional

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
    opts = {
        "quiet": True,
        "no_warnings": True,
    }
    if COOKIES_FILE.exists():
        opts["cookiefile"] = str(COOKIES_FILE)
    return opts


def get_video_info(url: str) -> VideoInfo:
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


def download_and_extract(
    url: str,
    output_format: AudioFormat = AudioFormat.MP3,
    quality: AudioQuality = AudioQuality.MEDIUM,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> tuple[Path, VideoInfo]:
    settings = get_settings()
    unique_id = str(uuid.uuid4())[:8]
    output_template = str(TEMP_DIR / f"{unique_id}_%(title).50s.%(ext)s")
    
    def progress_hook(d):
        if d["status"] == "downloading" and progress_callback:
            percent = 0
            if d.get("total_bytes"):
                percent = int(d.get("downloaded_bytes", 0) / d["total_bytes"] * 50)
            elif d.get("total_bytes_estimate"):
                percent = int(d.get("downloaded_bytes", 0) / d["total_bytes_estimate"] * 50)
            progress_callback("downloading", percent)
        elif d["status"] == "finished" and progress_callback:
            progress_callback("extracting", 60)
    
    def postprocessor_hook(d):
        if d["status"] == "started" and progress_callback:
            progress_callback("extracting", 70)
        elif d["status"] == "finished" and progress_callback:
            progress_callback("extracting", 90)
    
    ydl_opts = {
        **get_base_ydl_opts(),
        "outtmpl": output_template,
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
        # ESTO ES LO IMPORTANTE - descargar SOLO audio
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": output_format.value,
            "preferredquality": quality.value,
        }],
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        duration = info.get("duration", 0) or 0
        
        if duration > settings.max_duration_minutes * 60:
            raise ValueError(
                f"Video muy largo ({duration // 60} min). "
                f"Máximo permitido: {settings.max_duration_minutes} min"
            )
        
        video_info = VideoInfo(
            id=info.get("id", "unknown"),
            title=info.get("title", "Sin título"),
            duration_seconds=duration,
            duration_formatted=format_duration(duration),
            thumbnail=info.get("thumbnail"),
            source=info.get("extractor", "unknown"),
            channel=info.get("channel") or info.get("uploader"),
        )
        
        for file in TEMP_DIR.glob(f"{unique_id}_*"):
            if file.suffix == f".{output_format.value}":
                return file, video_info
    
    raise FileNotFoundError("No se encontró el archivo de audio generado")


def cleanup_file(file_path: Path) -> None:
    try:
        if file_path and file_path.exists():
            file_path.unlink()
    except Exception:
        pass


def cleanup_old_files(max_age_hours: int = 1) -> int:
    import time
    count = 0
    now = time.time()
    max_age_seconds = max_age_hours * 3600
    
    for file in TEMP_DIR.glob("*"):
        if now - file.stat().st_mtime > max_age_seconds:
            cleanup_file(file)
            count += 1
    return count
