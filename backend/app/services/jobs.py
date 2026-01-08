"""
Servicio de gestión de trabajos de extracción
"""
import asyncio
import time
from datetime import datetime

from ..models import (
    AudioFormat,
    AudioQuality,
    ExtractRequest,
    ExtractResult,
    JobResponse,
    JobStatus,
    VideoInfo,
)
from . import video, storage, db


def create_job(video_url: str, format: str, quality: str, source: str = "web") -> JobResponse:
    """Crea un nuevo job en Supabase"""
    job_data = db.create_job(
        video_url=video_url,
        format=format,
        quality=quality,
        source=source
    )
    
    return JobResponse(
        job_id=job_data["id"],
        status=JobStatus.PENDING,
        progress=0,
        message="Iniciando...",
        created_at=datetime.fromisoformat(job_data["created_at"].replace("Z", "+00:00")) if isinstance(job_data["created_at"], str) else job_data["created_at"],
    )


def get_job(job_id: str) -> JobResponse | None:
    """Obtiene un job de Supabase"""
    job_data = db.get_job(job_id)
    
    if not job_data:
        return None
    
    # Construir video_info si existe
    video_info = None
    if job_data.get("video_title"):
        video_info = VideoInfo(
            id=job_data.get("video_id", "unknown"),
            title=job_data["video_title"],
            duration_seconds=job_data.get("video_duration", 0),
            duration_formatted=video.format_duration(job_data.get("video_duration", 0)),
            thumbnail=job_data.get("video_thumbnail"),
            source=job_data.get("video_source", "unknown"),
            channel=job_data.get("video_channel"),
        )
    
    # Construir result si completado o fallido
    result = None
    if job_data["status"] == "completed" and job_data.get("audio_url"):
        result = ExtractResult(
            success=True,
            audio_url=job_data["audio_url"],
            file_size=job_data.get("file_size"),
            format=job_data.get("format", "mp3").upper(),
            quality=f"{job_data.get('quality', '192')} kbps",
        )
    elif job_data["status"] == "failed":
        result = ExtractResult(
            success=False,
            error=job_data.get("error_message", "Error desconocido"),
        )
    
    created_at = job_data["created_at"]
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    
    return JobResponse(
        job_id=job_data["id"],
        status=JobStatus(job_data["status"]),
        progress=job_data.get("progress", 0),
        message=job_data.get("stage", ""),
        created_at=created_at,
        video_info=video_info,
        result=result,
    )


def update_job(job_id: str, **kwargs) -> None:
    """Actualiza un job en Supabase"""
    db.update_job(job_id, **kwargs)


def delete_job(job_id: str) -> bool:
    """Elimina un job"""
    return db.delete_job(job_id)


def get_all_jobs(limit: int = 50) -> list[JobResponse]:
    """Obtiene todos los jobs"""
    jobs_data = db.list_jobs(limit=limit)
    return [get_job(j["id"]) for j in jobs_data if get_job(j["id"])]


def get_stats() -> dict:
    """Obtiene estadísticas de jobs"""
    return db.get_jobs_stats()


def cleanup_old_jobs(max_age_hours: int = 24) -> int:
    """Limpia jobs antiguos"""
    return db.cleanup_old_jobs(max_age_hours)


async def process_job(job_id: str, request: ExtractRequest) -> None:
    """
    Procesa un job de extracción de forma asíncrona
    """
    start_time = time.time()
    
    try:
        # 1. Obtener info del video
        update_job(job_id, status="processing", progress=5, stage="Obteniendo información del video...")
        
        info = await asyncio.to_thread(video.get_video_info, request.url)
        
        # Guardar info del video
        update_job(
            job_id,
            progress=10,
            video_title=info.title,
            video_id=info.id,
            video_duration=info.duration_seconds,
            video_thumbnail=info.thumbnail,
            video_source=info.source,
            video_channel=info.channel,
        )
        
        # 2. Callback para progreso
        def on_progress(stage: str, percent: int):
            if stage == "downloading":
                update_job(job_id, status="downloading", progress=10 + percent, stage="Descargando video...")
            elif stage == "extracting":
                update_job(job_id, status="extracting", progress=percent, stage="Extrayendo audio...")
        
        # 3. Descargar y extraer
        update_job(job_id, status="downloading", progress=15, stage="Descargando video...")
        
        audio_file, video_info = await asyncio.to_thread(
            video.download_and_extract,
            request.url,
            request.format,
            request.quality,
            on_progress,
        )
        
        # 4. Subir a Supabase
        update_job(job_id, status="uploading", progress=92, stage="Subiendo a la nube...")
        
        audio_url = await asyncio.to_thread(storage.upload_file, audio_file)
        
        # 5. Obtener tamaño del archivo
        file_size = video.format_file_size(audio_file.stat().st_size)
        
        # 6. Limpiar archivo temporal
        video.cleanup_file(audio_file)
        
        # 7. Calcular tiempo de procesamiento
        processing_time = round(time.time() - start_time, 2)
        
        # 8. Completar job
        update_job(
            job_id,
            status="completed",
            progress=100,
            stage="¡Audio extraído exitosamente!",
            audio_url=audio_url,
            file_size=file_size,
            processing_time=processing_time,
        )
        
    except Exception as e:
        processing_time = round(time.time() - start_time, 2)
        
        update_job(
            job_id,
            status="failed",
            progress=0,
            stage="Error",
            error_code="EXTRACTION_FAILED",
            error_message=str(e),
            processing_time=processing_time,
        )
