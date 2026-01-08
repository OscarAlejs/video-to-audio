"""
Rutas de la API
"""
import time
import asyncio
from fastapi import APIRouter, BackgroundTasks, HTTPException

from .config import get_settings
from .models import (
    ExtractRequest,
    HealthResponse,
    JobResponse,
    ProcessRequest,
    ProcessResponse,
    StatsResponse,
    VideoInfo,
)
from .services import jobs, storage, video, db
from . import __version__


router = APIRouter()


# ============== Health ==============

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Estado del servicio"""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        version=__version__,
        supabase_configured=storage.is_configured(),
        max_duration_minutes=settings.max_duration_minutes,
    )


# ============== Video Info ==============

@router.get("/info", response_model=VideoInfo)
async def get_video_info(url: str):
    """Obtiene información de un video sin descargarlo"""
    try:
        info = video.get_video_info(url)
        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== API Mode - Synchronous Processing ==============

@router.post("/process", response_model=ProcessResponse)
async def process_video(request: ProcessRequest):
    """
    **Modo API** - Procesa un video de forma síncrona.
    Guarda el job en Supabase para auditoría.
    """
    start_time = time.time()
    settings = get_settings()
    
    if not storage.is_configured():
        return ProcessResponse(
            status="error",
            error_code="SUPABASE_NOT_CONFIGURED",
            message="Supabase no está configurado"
        )
    
    # Crear job en Supabase
    job_data = db.create_job(
        video_url=request.video_url,
        format=request.format.value,
        quality=request.quality.value,
        source="api"
    )
    job_id = job_data["id"]
    
    try:
        # 1. Obtener info del video
        db.update_job(job_id, status="processing", progress=10, stage="Obteniendo información...")
        
        video_info = await asyncio.to_thread(video.get_video_info, request.video_url)
        
        # Guardar info del video
        db.update_job(
            job_id,
            video_title=video_info.title,
            video_id=video_info.id,
            video_duration=video_info.duration_seconds,
            video_thumbnail=video_info.thumbnail,
            video_source=video_info.source,
            video_channel=video_info.channel,
        )
        
        # 2. Verificar duración
        if video_info.duration_seconds > settings.max_duration_minutes * 60:
            db.update_job(
                job_id,
                status="failed",
                error_code="VIDEO_TOO_LONG",
                error_message=f"Video muy largo ({video_info.duration_seconds // 60} min)"
            )
            return ProcessResponse(
                status="error",
                error_code="VIDEO_TOO_LONG",
                message=f"Video muy largo ({video_info.duration_seconds // 60} min). Máximo: {settings.max_duration_minutes} min",
                video_info=video_info,
            )
        
        # 3. Descargar y extraer
        db.update_job(job_id, status="downloading", progress=30, stage="Descargando...")
        
        audio_file, video_info = await asyncio.to_thread(
            video.download_and_extract,
            request.video_url,
            request.format,
            request.quality,
            None,
        )
        
        # 4. Subir a Supabase
        db.update_job(job_id, status="uploading", progress=80, stage="Subiendo...")
        
        audio_url = await asyncio.to_thread(storage.upload_file, audio_file)
        
        # 5. Obtener tamaño
        file_size = audio_file.stat().st_size
        file_size_formatted = video.format_file_size(file_size)
        
        # 6. Limpiar archivo temporal
        video.cleanup_file(audio_file)
        
        # 7. Calcular tiempo
        processing_time = round(time.time() - start_time, 2)
        
        # 8. Actualizar job como completado
        db.update_job(
            job_id,
            status="completed",
            progress=100,
            stage="Completado",
            audio_url=audio_url,
            file_size=file_size_formatted,
            processing_time=processing_time,
        )
        
        return ProcessResponse(
            status="success",
            audio_url=audio_url,
            video_info=video_info,
            file_size=file_size,
            file_size_formatted=file_size_formatted,
            duration=video_info.duration_seconds,
            duration_formatted=video_info.duration_formatted,
            format=request.format.value,
            quality=request.quality.value,
            processing_time=processing_time,
            message="Audio extraído exitosamente",
        )
        
    except Exception as e:
        processing_time = round(time.time() - start_time, 2)
        
        db.update_job(
            job_id,
            status="failed",
            error_code="INTERNAL_ERROR",
            error_message=str(e),
            processing_time=processing_time,
        )
        
        return ProcessResponse(
            status="error",
            error_code="INTERNAL_ERROR",
            message=str(e),
            processing_time=processing_time,
        )


# ============== Extraction (Async) ==============

@router.post("/extract", response_model=JobResponse)
async def start_extraction(request: ExtractRequest, background_tasks: BackgroundTasks):
    """Inicia extracción asíncrona - retorna job_id para polling"""
    if not storage.is_configured():
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    
    job = jobs.create_job(
        video_url=request.url,
        format=request.format.value,
        quality=request.quality.value,
        source="web"
    )
    
    background_tasks.add_task(jobs.process_job, job.job_id, request)
    
    return job


# ============== Jobs ==============

@router.get("/jobs", response_model=list[JobResponse])
async def list_jobs():
    """Lista todos los jobs"""
    return jobs.get_all_jobs()


@router.get("/jobs/stats", response_model=StatsResponse)
async def get_job_stats():
    """Estadísticas de jobs"""
    stats = jobs.get_stats()
    return StatsResponse(
        total_jobs=stats["total"],
        completed_jobs=stats["completed"],
        failed_jobs=stats["failed"],
        active_jobs=stats["processing"] + stats["pending"],
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Obtiene estado de un job"""
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return job


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Elimina un job"""
    if jobs.delete_job(job_id):
        return {"message": "Job eliminado"}
    raise HTTPException(status_code=404, detail="Job no encontrado")


# ============== Logs (ahora desde jobs table) ==============

@router.get("/logs")
async def get_logs(limit: int = 50):
    """Obtiene historial de jobs"""
    jobs_list = db.list_jobs(limit=limit)
    return {"total": len(jobs_list), "logs": jobs_list}


@router.get("/logs/api")
async def get_api_logs(limit: int = 50):
    """Jobs desde API"""
    jobs_list = db.list_jobs(source="api", limit=limit)
    return {"total": len(jobs_list), "logs": jobs_list}


@router.get("/logs/web")
async def get_web_logs(limit: int = 50):
    """Jobs desde Web"""
    jobs_list = db.list_jobs(source="web", limit=limit)
    return {"total": len(jobs_list), "logs": jobs_list}


@router.get("/logs/errors")
async def get_error_logs(limit: int = 50):
    """Jobs con errores"""
    jobs_list = db.list_jobs(status="failed", limit=limit)
    return {"total": len(jobs_list), "logs": jobs_list}


@router.get("/logs/stats")
async def get_logs_stats():
    """Estadísticas"""
    return db.get_jobs_stats()


# ============== Maintenance ==============

@router.post("/cleanup")
async def cleanup():
    """Limpia archivos y jobs antiguos"""
    files_cleaned = video.cleanup_old_files()
    jobs_cleaned = jobs.cleanup_old_jobs()
    return {"files_cleaned": files_cleaned, "jobs_cleaned": jobs_cleaned}
