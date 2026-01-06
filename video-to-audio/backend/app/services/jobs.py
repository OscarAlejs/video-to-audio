"""
Servicio de gestión de trabajos de extracción
"""
import asyncio
import time
from datetime import datetime
from typing import Optional
from uuid import uuid4

from ..models import (
    AudioFormat,
    AudioQuality,
    ExecutionSource,
    ExtractRequest,
    ExtractResult,
    JobResponse,
    JobStatus,
    VideoInfo,
)
from . import video, storage, logs


# Almacén en memoria de jobs (en producción usar Redis)
_jobs: dict[str, JobResponse] = {}


def create_job() -> JobResponse:
    """Crea un nuevo job"""
    job = JobResponse(
        job_id=str(uuid4()),
        status=JobStatus.PENDING,
        progress=0,
        message="Iniciando...",
        created_at=datetime.now(),
    )
    _jobs[job.job_id] = job
    return job


def get_job(job_id: str) -> Optional[JobResponse]:
    """Obtiene un job por ID"""
    return _jobs.get(job_id)


def update_job(
    job_id: str,
    status: Optional[JobStatus] = None,
    progress: Optional[int] = None,
    message: Optional[str] = None,
    video_info: Optional[VideoInfo] = None,
    result: Optional[ExtractResult] = None,
) -> Optional[JobResponse]:
    """Actualiza un job existente"""
    job = _jobs.get(job_id)
    if not job:
        return None
    
    if status is not None:
        job.status = status
    if progress is not None:
        job.progress = progress
    if message is not None:
        job.message = message
    if video_info is not None:
        job.video_info = video_info
    if result is not None:
        job.result = result
    
    return job


def delete_job(job_id: str) -> bool:
    """Elimina un job"""
    if job_id in _jobs:
        del _jobs[job_id]
        return True
    return False


def get_all_jobs() -> list[JobResponse]:
    """Obtiene todos los jobs"""
    return list(_jobs.values())


def get_stats() -> dict:
    """Obtiene estadísticas de jobs"""
    jobs = list(_jobs.values())
    return {
        "total_jobs": len(jobs),
        "completed_jobs": sum(1 for j in jobs if j.status == JobStatus.COMPLETED),
        "failed_jobs": sum(1 for j in jobs if j.status == JobStatus.FAILED),
        "active_jobs": sum(1 for j in jobs if j.status in [JobStatus.PENDING, JobStatus.PROCESSING, JobStatus.DOWNLOADING, JobStatus.EXTRACTING, JobStatus.UPLOADING]),
    }


def cleanup_old_jobs(max_age_hours: int = 24) -> int:
    """Limpia jobs antiguos"""
    now = datetime.now()
    to_delete = []
    
    for job_id, job in _jobs.items():
        age = (now - job.created_at).total_seconds() / 3600
        if age > max_age_hours and job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            to_delete.append(job_id)
    
    for job_id in to_delete:
        del _jobs[job_id]
    
    return len(to_delete)


async def process_job(job_id: str, request: ExtractRequest) -> None:
    """
    Procesa un job de extracción de forma asíncrona
    """
    start_time = time.time()
    video_info = None
    
    try:
        # 1. Obtener info del video
        update_job(job_id, status=JobStatus.PROCESSING, progress=5, message="Obteniendo información del video...")
        
        info = await asyncio.to_thread(video.get_video_info, request.url)
        video_info = info
        update_job(job_id, progress=10, video_info=info)
        
        # 2. Callback para progreso
        def on_progress(stage: str, percent: int):
            if stage == "downloading":
                update_job(job_id, status=JobStatus.DOWNLOADING, progress=10 + percent, message="Descargando video...")
            elif stage == "extracting":
                update_job(job_id, status=JobStatus.EXTRACTING, progress=percent, message="Extrayendo audio...")
        
        # 3. Descargar y extraer
        update_job(job_id, status=JobStatus.DOWNLOADING, progress=15, message="Descargando video...")
        
        audio_file, video_info = await asyncio.to_thread(
            video.download_and_extract,
            request.url,
            request.format,
            request.quality,
            on_progress,
        )
        
        update_job(job_id, video_info=video_info)
        
        # 4. Subir a Supabase
        update_job(job_id, status=JobStatus.UPLOADING, progress=92, message="Subiendo a la nube...")
        
        audio_url = await asyncio.to_thread(storage.upload_file, audio_file)
        
        # 5. Obtener tamaño del archivo
        file_size = video.format_file_size(audio_file.stat().st_size)
        
        # 6. Limpiar archivo temporal
        video.cleanup_file(audio_file)
        
        # 7. Calcular tiempo de procesamiento
        processing_time = round(time.time() - start_time, 2)
        
        # 8. Registrar log de éxito (WEB)
        logs.add_log(
            source=ExecutionSource.WEB,
            video_url=request.url,
            status="success",
            video_title=video_info.title,
            audio_url=audio_url,
            file_size_formatted=file_size,
            duration_formatted=video_info.duration_formatted,
            format=request.format.value,
            quality=request.quality.value,
            processing_time=processing_time,
        )
        
        # 9. Completar job
        update_job(
            job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            message="¡Audio extraído exitosamente!",
            result=ExtractResult(
                success=True,
                audio_url=audio_url,
                filename=audio_file.name,
                file_size=file_size,
                format=request.format.value.upper(),
                quality=f"{request.quality.value} kbps",
            )
        )
        
    except Exception as e:
        processing_time = round(time.time() - start_time, 2)
        
        # Registrar log de error (WEB)
        logs.add_log(
            source=ExecutionSource.WEB,
            video_url=request.url,
            status="error",
            video_title=video_info.title if video_info else None,
            error_code="EXTRACTION_FAILED",
            error_message=str(e),
            processing_time=processing_time,
        )
        
        update_job(
            job_id,
            status=JobStatus.FAILED,
            progress=0,
            message=f"Error: {str(e)}",
            result=ExtractResult(
                success=False,
                error=str(e),
            )
        )
