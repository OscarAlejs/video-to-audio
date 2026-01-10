"""
Servicio de extracción de audio desde archivos de video subidos
"""
import uuid
import subprocess
from pathlib import Path
from typing import Optional

from ..config import get_settings
from ..models import AudioFormat, AudioQuality


TEMP_DIR = Path("/tmp/video-to-audio")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Formatos de video soportados
SUPPORTED_VIDEO_FORMATS = {
    ".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".wmv", ".m4v", ".mpeg", ".mpg", ".3gp"
}


def is_valid_video_file(filename: str) -> bool:
    """Verifica si el archivo es un formato de video soportado"""
    ext = Path(filename).suffix.lower()
    return ext in SUPPORTED_VIDEO_FORMATS


def get_video_duration(file_path: Path) -> Optional[int]:
    """Obtiene la duración del video en segundos usando ffprobe"""
    try:
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


def extract_audio_from_file(
    input_file: Path,
    output_format: AudioFormat = AudioFormat.MP3,
    quality: AudioQuality = AudioQuality.MEDIUM,
) -> Path:
    """
    Extrae audio de un archivo de video usando FFmpeg.
    
    Args:
        input_file: Ruta al archivo de video
        output_format: Formato de salida (mp3, m4a, wav, opus)
        quality: Calidad del audio (128, 192, 256, 320 kbps)
    
    Returns:
        Path al archivo de audio generado
    """
    settings = get_settings()
    
    # Verificar duración
    duration = get_video_duration(input_file)
    if duration and duration > settings.max_duration_minutes * 60:
        raise ValueError(
            f"Video muy largo ({duration // 60} min). "
            f"Máximo permitido: {settings.max_duration_minutes} min"
        )
    
    # Generar nombre de salida
    unique_id = str(uuid.uuid4())[:8]
    stem = input_file.stem[:50]  # Limitar longitud del nombre
    output_file = TEMP_DIR / f"{unique_id}_{stem}.{output_format.value}"
    
    # Configurar codec según formato
    codec_args = []
    if output_format == AudioFormat.MP3:
        codec_args = ["-codec:a", "libmp3lame", "-b:a", f"{quality.value}k"]
    elif output_format == AudioFormat.M4A:
        codec_args = ["-codec:a", "aac", "-b:a", f"{quality.value}k"]
    elif output_format == AudioFormat.WAV:
        codec_args = ["-codec:a", "pcm_s16le"]
    elif output_format == AudioFormat.OPUS:
        codec_args = ["-codec:a", "libopus", "-b:a", f"{quality.value}k"]
    
    # Ejecutar FFmpeg
    cmd = [
        "ffmpeg",
        "-i", str(input_file),
        "-vn",  # Sin video
        "-y",   # Sobrescribir
        *codec_args,
        str(output_file)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minutos máximo
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg error: {result.stderr}")
        
        if not output_file.exists():
            raise FileNotFoundError("FFmpeg no generó el archivo de audio")
        
        return output_file
        
    except subprocess.TimeoutExpired:
        raise RuntimeError("Timeout: La extracción tardó demasiado")
    except Exception as e:
        # Limpiar archivo parcial si existe
        if output_file.exists():
            output_file.unlink()
        raise e


def cleanup_file(file_path: Path) -> None:
    """Elimina un archivo temporal"""
    try:
        if file_path and file_path.exists():
            file_path.unlink()
    except Exception:
        pass


def format_file_size(bytes_size: int) -> str:
    """Formatea tamaño de archivo"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"
