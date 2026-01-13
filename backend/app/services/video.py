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
    """Opciones optimizadas - balance velocidad/estabilidad"""
    opts = {
        "quiet": True,
        "no_warnings": True,
        # === HTTP/1.1 para evitar ConnectionTerminated ===
        "legacy_server_connect": True,
        # === VELOCIDAD + ESTABILIDAD ===
        "concurrent_fragment_downloads": 3,  # Balance: 3 fragmentos
        "retries": 15,
        "fragment_retries": 15,
        "socket_timeout": 45,
        "http_chunk_size": 10485760,  # 10MB chunks
        # === HEADERS ===
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "*/*",
            "Connection": "keep-alive",
        },
        # === EXTRACTORS ===
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
            },
            "vimeo": {"http_version": "1.1"},
        },
    }
    if COOKIES_FILE.exists():
        opts["cookiefile"] = str(COOKIES_FILE)
    return opts


def is_direct_file_url(url: str) -> bool:
    """Detecta si es una URL directa de archivo"""
    video_extensions = [".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".wmv", ".m4v", ".mpeg", ".mpg", ".3gp"]
    
    if any(url.lower().endswith(ext) for ext in video_extensions):
        return True
    
    if "supabase.co/storage" in url.lower():
        return True
    
    return False


def download_direct_file(url: str, output_path: Path) -> Path:
    """Descarga un archivo directo desde una URL"""
    print(f"📥 Descargando archivo directo: {url}")
    
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        if progress % 10 < 1:
                            print(f"   📥 Descarga: {progress:.0f}%")
        
        print(f"✅ Descarga completada: {output_path.name}")
        return output_path
        
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Error descargando archivo: {str(e)}")


def get_video_duration_from_file(file_path: Path) -> Optional[int]:
    """Obtiene duración de un archivo de video usando ffprobe"""
    try:
        import subprocess
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(file_path)
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(float(result.stdout.strip()))
    except Exception:
        pass
    return None


def get_video_info(url: str) -> VideoInfo:
    """Obtiene información del video (YouTube/Vimeo o archivo directo)"""
    
    if is_direct_file_url(url):
        filename = urlparse(url).path.split('/')[-1]
        return VideoInfo(
            id="direct_file",
            title=filename,
            duration_seconds=0,
            duration_formatted="Desconocida",
            thumbnail=None,
            source="direct_url",
            channel=None,
        )
    
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
    
    # === ARCHIVO DIRECTO ===
    if is_direct_file_url(url):
        print(f"🔗 Procesando URL directa: {url}")
        
        filename = urlparse(url).path.split('/')[-1] or f"video_{unique_id}.mp4"
        temp_video = TEMP_DIR / f"{unique_id}_{filename}"
        
        if progress_callback:
            progress_callback("downloading", 10)
        
        download_direct_file(url, temp_video)
        
        if progress_callback:
            progress_callback("downloading", 50)
        
        duration = get_video_duration_from_file(temp_video)
        
        if duration and duration > settings.max_duration_minutes * 60:
            cleanup_file(temp_video)
            raise ValueError(
                f"Video muy largo ({duration // 60} min). "
                f"Máximo permitido: {settings.max_duration_minutes} min"
            )
        
        if progress_callback:
            progress_callback("extracting", 60)
        
        from . import upload
        audio_file = upload.extract_audio_from_file(
            temp_video,
            output_format,
            quality
        )
        
        if progress_callback:
            progress_callback("extracting", 90)
        
        cleanup_file(temp_video)
        
        video_info = VideoInfo(
            id="direct_file",
            title=filename,
            duration_seconds=duration or 0,
            duration_formatted=format_duration(duration) if duration else "Desconocida",
            thumbnail=None,
            source="direct_url",
            channel=None,
        )
        
        return audio_file, video_info
    
    # === YOUTUBE/VIMEO ===
    output_template = str(TEMP_DIR / f"{unique_id}_%(title).50s.%(ext)s")
    
    print(f"🎬 Descargando video de {url}")
    
    def progress_hook(d):
        if d["status"] == "downloading":
            if progress_callback:
                percent = 0
                if d.get("total_bytes"):
                    percent = int(d.get("downloaded_bytes", 0) / d["total_bytes"] * 50)
                elif d.get("total_bytes_estimate"):
                    percent = int(d.get("downloaded_bytes", 0) / d["total_bytes_estimate"] * 50)
                progress_callback("downloading", percent)
            
            # Log cada 20%
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                downloaded = d.get("downloaded_bytes", 0)
                percent = int(downloaded / total * 100)
                if percent % 20 == 0:
                    speed = d.get("speed", 0) or 0
                    speed_str = f"{speed/1024:.0f} KB/s" if speed < 1024*1024 else f"{speed/1024/1024:.1f} MB/s"
                    print(f"   📥 {percent}% - {speed_str}")
                    
        elif d["status"] == "finished":
            print(f"   ✅ Descarga completada")
            if progress_callback:
                progress_callback("extracting", 60)
    
    def postprocessor_hook(d):
        if d["status"] == "started":
            print(f"   🎵 Extrayendo audio...")
            if progress_callback:
                progress_callback("extracting", 70)
        elif d["status"] == "finished":
            print(f"   ✅ Audio extraído")
            if progress_callback:
                progress_callback("extracting", 90)
    
    ydl_opts = {
        **get_base_ydl_opts(),
        "outtmpl": output_template,
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
        # === FORMATO FLEXIBLE - acepta cualquier cosa ===
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
                print(f"✅ Proceso completado: {video_info.title}")
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
