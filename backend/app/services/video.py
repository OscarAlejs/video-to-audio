"""
Servicio de descarga y extracción de audio
"""
import asyncio
import uuid
import requests
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

import yt_dlp

from .. config import get_settings
from ..models import AudioFormat, AudioQuality, VideoInfo


TEMP_DIR = Path("/tmp/video-to-audio")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

COOKIES_FILE = Path("/app/cookies.txt")

# Semáforo global para limitar descargas concurrentes de YouTube/Vimeo
# Máximo 2 descargas simultáneas para evitar ConnectionTerminated
_download_semaphore = asyncio. Semaphore(2)


def format_duration(seconds: int) -> str:
    if not seconds:
        return "0:00"
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours: 
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs: 02d}"


def format_file_size(bytes_size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024: 
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def get_base_ydl_opts() -> dict:
    """Opciones base - estabilidad y rate limiting"""
    opts = {
        "quiet": True,
        "no_warnings": True,
        # === ESTABILIDAD ===
        "concurrent_fragment_downloads": 1,  # Sin concurrencia (evita ConnectionTerminated)
        "retries": 10,
        "fragment_retries": 10,
        "socket_timeout": 30,
        "http_chunk_size": 10485760,  # 10MB - refresca conexiones periódicamente
        # === RATE LIMITING ===
        "sleep_interval": 1,
        "max_sleep_interval": 5,
        "sleep_interval_requests": 1,
        # === FIX HTTP/2 ===
        "legacy_server_connect": True,
        "extractor_args": {
            "youtube":  {
                "player_client":  "android",
                "player_skip":  ["web"],
            },
            "vimeo":  {"http_version": "1.1"},
        },
    }
    if COOKIES_FILE.exists():
        opts["cookiefile"] = str(COOKIES_FILE)
    return opts


def is_direct_file_url(url: str) -> bool:
    """Detecta si es una URL directa de archivo"""
    video_extensions = [". mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".wmv", ".m4v", ". mpeg", ".mpg", ".3gp"]
    
    # Extensión en URL
    if any(url.lower().endswith(ext) for ext in video_extensions):
        return True
    
    # URLs de Supabase Storage
    if "supabase. co/storage" in url. lower():
        return True
    
    return False


def download_direct_file(url: str, output_path: Path) -> Path:
    """
    Descarga un archivo directo desde una URL
    """
    print(f"📥 Descargando archivo directo: {url}")
    
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
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
        
        print(f"✅ Descarga completada:  {output_path. name}")
        return output_path
        
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Error descargando archivo:  {str(e)}")


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
        if result.returncode == 0 and result.stdout. strip():
            return int(float(result.stdout.strip()))
    except Exception:
        pass
    return None


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
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        duration = info.get("duration", 0) or 0
        
        return VideoInfo(
            id=info.get("id", "unknown"),
            title=info.get("title", "Sin título"),
            duration_seconds=duration,
            duration_formatted=format_duration(duration),
            thumbnail=info. get("thumbnail"),
            source=info.get("extractor", "unknown"),
            channel=info. get("channel") or info.get("uploader"),
        )


async def download_and_extract(
    url: str,
    output_format: AudioFormat = AudioFormat.MP3,
    quality: AudioQuality = AudioQuality.MEDIUM,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> tuple[Path, VideoInfo]: 
    settings = get_settings()
    unique_id = str(uuid.uuid4())[:8]
    
    # Detectar si es archivo directo (sin semáforo - no afectan a YouTube)
    if is_direct_file_url(url):
        print(f"🔗 Procesando URL directa: {url}")
        
        # Descargar archivo
        filename = urlparse(url).path.split('/')[-1] or f"video_{unique_id}. mp4"
        temp_video = TEMP_DIR / f"{unique_id}_{filename}"
        
        if progress_callback:
            progress_callback("downloading", 10)
        
        await asyncio.to_thread(download_direct_file, url, temp_video)
        
        if progress_callback:
            progress_callback("downloading", 50)
        
        # Obtener duración del archivo descargado
        duration = await asyncio.to_thread(get_video_duration_from_file, temp_video)
        
        # Validar duración
        if duration and duration > settings.max_duration_minutes * 60:
            cleanup_file(temp_video)
            raise ValueError(
                f"Video muy largo ({duration // 60} min). "
                f"Máximo permitido: {settings.max_duration_minutes} min"
            )
        
        # Extraer audio usando función del módulo upload
        if progress_callback:
            progress_callback("extracting", 60)
        
        from .  import upload
        audio_file = await asyncio.to_thread(
            upload.extract_audio_from_file,
            temp_video,
            output_format,
            quality
        )
        
        if progress_callback:
            progress_callback("extracting", 90)
        
        # Limpiar video temporal
        cleanup_file(temp_video)
        
        # Crear VideoInfo
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
    
    # YouTube/Vimeo (CON semáforo para limitar concurrencia)
    async with _download_semaphore: 
        active_downloads = 2 - _download_semaphore._value
        print(f"🎬 Descargando video de {url} (descargas activas: {active_downloads}/2)")
        
        output_template = str(TEMP_DIR / f"{unique_id}_%(title).50s.%(ext)s")
        
        def progress_hook(d):
            if d["status"] == "downloading":
                if progress_callback:
                    percent = 0
                    if d.get("total_bytes"):
                        percent = int(d. get("downloaded_bytes", 0) / d["total_bytes"] * 50)
                    elif d.get("total_bytes_estimate"):
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
            # === FORMATO ===
            "format": "worstvideo+bestaudio/bestaudio/worst",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": output_format.value,
                "preferredquality": quality.value,
            }],
        }
        
        def _download():
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
        
        return await asyncio.to_thread(_download)


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
        if now - file. stat().st_mtime > max_age_seconds:
            cleanup_file(file)
            count += 1
    return count
