"""
Modelos de datos
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, field_validator


class AudioFormat(str, Enum):
    MP3 = "mp3"
    M4A = "m4a"
    WAV = "wav"
    OPUS = "opus"


class AudioQuality(str, Enum):
    LOW = "128"
    MEDIUM = "192"
    HIGH = "256"
    BEST = "320"


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DOWNLOADING = "downloading"
    EXTRACTING = "extracting"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"


# ============== Requests ==============

class ExtractRequest(BaseModel):
    url: str
    format: AudioFormat = AudioFormat.MP3
    quality: AudioQuality = AudioQuality.MEDIUM
    
    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        
        # Soportar YouTube/Vimeo
        video_platforms = ["youtube.com", "youtu.be", "vimeo.com"]
        if any(domain in v.lower() for domain in video_platforms):
            return v
        
        # Soportar URLs directas de archivos de video
        video_extensions = [".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".wmv", ".m4v", ".mpeg", ".mpg", ".3gp"]
        if any(v.lower().endswith(ext) for ext in video_extensions):
            return v
        
        # Soportar URLs de Supabase Storage (pueden no tener extensión visible)
        if "supabase.co/storage" in v.lower():
            return v
        
        raise ValueError("Solo se soportan URLs de YouTube, Vimeo o archivos de video directos (.mp4, .mkv, .webm, etc.)")



class ProcessRequest(BaseModel):
    """Request para el endpoint síncrono /process"""
    video_url: str
    format: AudioFormat = AudioFormat.MP3
    quality: AudioQuality = AudioQuality.MEDIUM
    
    @field_validator("video_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        
        # Soportar YouTube/Vimeo
        video_platforms = ["youtube.com", "youtu.be", "vimeo.com"]
        if any(domain in v.lower() for domain in video_platforms):
            return v
        
        # Soportar URLs directas de archivos de video
        video_extensions = [".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".wmv", ".m4v", ".mpeg", ".mpg", ".3gp"]
        if any(v.lower().endswith(ext) for ext in video_extensions):
            return v
        
        # Soportar URLs de Supabase Storage
        if "supabase.co/storage" in v.lower():
            return v
        
        raise ValueError("Solo se soportan URLs de YouTube, Vimeo o archivos de video directos (.mp4, .mkv, .webm, etc.)")


# ============== Responses ==============

class VideoInfo(BaseModel):
    id: Optional[str] = None  # ✅ CAMBIO: Ahora es opcional
    title: Optional[str] = None  # Ya era opcional
    duration_seconds: Optional[int] = None  # Ya era opcional
    duration_formatted:  Optional[str] = None  # Ya era opcional
    thumbnail: Optional[str] = None
    source: Optional[str] = None  # ✅ CAMBIO:  Ahora es opcional
    channel:  Optional[str] = None


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress:  int = 0  # 0-100
    message: str = ""
    created_at:  datetime
    video_info: Optional[VideoInfo] = None
    result:  Optional["ExtractResult"] = None


class ExtractResult(BaseModel):
    success: bool
    audio_url: Optional[str] = None
    filename: Optional[str] = None
    file_size: Optional[str] = None
    format: Optional[str] = None
    quality: Optional[str] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    supabase_configured: bool
    max_duration_minutes:  int


class StatsResponse(BaseModel):
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    active_jobs:  int


class ProcessResponse(BaseModel):
    """Respuesta del endpoint síncrono /process"""
    status:  str  # "success" o "error"
    audio_url: Optional[str] = None
    video_info: Optional[VideoInfo] = None
    file_size: Optional[int] = None
    file_size_formatted: Optional[str] = None
    duration: Optional[int] = None
    duration_formatted: Optional[str] = None
    format: Optional[str] = None
    quality: Optional[str] = None
    processing_time: Optional[float] = None
    error_code: Optional[str] = None
    message: Optional[str] = None


class UploadResponse(BaseModel):
    """Respuesta del endpoint /upload"""
    status: str  # "success" o "error"
    audio_url: Optional[str] = None
    filename: Optional[str] = None
    file_size: Optional[int] = None
    file_size_formatted: Optional[str] = None
    original_size: Optional[int] = None
    original_size_formatted: Optional[str] = None
    duration: Optional[int] = None
    duration_formatted: Optional[str] = None
    format: Optional[str] = None
    quality: Optional[str] = None
    processing_time: Optional[float] = None
    job_id: Optional[str] = None
    error_code: Optional[str] = None
    message: Optional[str] = None


# ============== Execution Logs ==============

class ExecutionSource(str, Enum):
    API = "api"
    WEB = "web"


class ExecutionLog(BaseModel):
    """Log de una ejecución"""
    id:  str
    source: ExecutionSource
    timestamp: datetime
    video_url: str
    video_title: Optional[str] = None
    status:  str  # "success" o "error"
    audio_url:  Optional[str] = None
    file_size_formatted: Optional[str] = None
    duration_formatted: Optional[str] = None
    format: Optional[str] = None
    quality: Optional[str] = None
    processing_time: Optional[float] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class LogsResponse(BaseModel):
    """Respuesta de logs"""
    total: int
    logs: list[ExecutionLog]


# Para referencias circulares
JobResponse.model_rebuild()
