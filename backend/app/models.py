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
        supported = ["youtube.com", "youtu.be", "vimeo.com"]
        if not any(domain in v.lower() for domain in supported):
            raise ValueError("Solo se soportan URLs de YouTube o Vimeo")
        return v.strip()


class ProcessRequest(BaseModel):
    """Request para el endpoint síncrono /process"""
    video_url: str
    format: AudioFormat = AudioFormat.MP3
    quality: AudioQuality = AudioQuality.MEDIUM
    
    @field_validator("video_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        supported = ["youtube.com", "youtu.be", "vimeo.com"]
        if not any(domain in v.lower() for domain in supported):
            raise ValueError("Solo se soportan URLs de YouTube o Vimeo")
        return v.strip()


# ============== Responses ==============

class VideoInfo(BaseModel):
    id: str
    title: str
    duration_seconds: int
    duration_formatted: str
    thumbnail: Optional[str] = None
    source: str
    channel: Optional[str] = None


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = 0  # 0-100
    message: str = ""
    created_at: datetime
    video_info: Optional[VideoInfo] = None
    result: Optional["ExtractResult"] = None


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
    max_duration_minutes: int


class StatsResponse(BaseModel):
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    active_jobs: int


class ProcessResponse(BaseModel):
    """Respuesta del endpoint síncrono /process"""
    status: str  # "success" o "error"
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


# ============== Execution Logs ==============

class ExecutionSource(str, Enum):
    API = "api"
    WEB = "web"


class ExecutionLog(BaseModel):
    """Log de una ejecución"""
    id: str
    source: ExecutionSource
    timestamp: datetime
    video_url: str
    video_title: Optional[str] = None
    status: str  # "success" o "error"
    audio_url: Optional[str] = None
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
