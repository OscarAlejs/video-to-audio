"""
Rutas de la API
"""
import time
import asyncio
from fastapi import APIRouter, BackgroundTasks, HTTPException

from .config import get_settings
from .models import (
    ExecutionLog,
    ExecutionSource,
    ExtractRequest,
    HealthResponse,
    JobResponse,
    LogsResponse,
    ProcessRequest,
    ProcessResponse,
    StatsResponse,
    VideoInfo,
)
from .services import jobs, storage, video, logs
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
    """
    Obtiene información de un video sin descargarlo
    
    - **url**: URL de YouTube o Vimeo
    """
    try:
        info = video.get_video_info(url)
        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== API Mode - Synchronous Processing ==============

@router.post("/process", response_model=ProcessResponse)
async def process_video(request: ProcessRequest):
    """
    **Modo API** - Procesa un video de forma síncrona y retorna la URL del audio.
    
    Este endpoint espera a que termine todo el proceso y devuelve el resultado directamente.
    Ideal para integraciones con n8n, Make, Zapier, etc.
    
    **Request:**
    ```json
    {
        "video_url": "https://youtube.com/watch?v=...",
        "format": "mp3",
        "quality": "192"
    }
    ```
    
    **Response (success):**
    ```json
    {
        "status": "success",
        "audio_url": "https://xxx.supabase.co/storage/...",
        "video_info": {...},
        "file_size": 4567890,
        "duration": 180,
        "format": "mp3",
        "quality": "192",
        "processing_time": 45.2
    }
    ```
    
    **Timeout:** Este endpoint puede tardar varios minutos dependiendo del video.
    Configura timeout alto en tu cliente HTTP (recomendado: 5-10 minutos).
    """
    start_time = time.time()
    settings = get_settings()
    
    # Verificar Supabase
    if not storage.is_configured():
        return ProcessResponse(
            status="error",
            error_code="SUPABASE_NOT_CONFIGURED",
            message="Supabase no está configurado. Define SUPABASE_URL y SUPABASE_KEY"
        )
    
    try:
        # 1. Obtener info del video
        video_info = await asyncio.to_thread(video.get_video_info, request.video_url)
        
        # 2. Verificar duración
        if video_info.duration_seconds > settings.max_duration_minutes * 60:
            return ProcessResponse(
                status="error",
                error_code="VIDEO_TOO_LONG",
                message=f"Video muy largo ({video_info.duration_seconds // 60} min). Máximo: {settings.max_duration_minutes} min",
                video_info=video_info,
            )
        
        # 3. Descargar y extraer audio
        audio_file, video_info = await asyncio.to_thread(
            video.download_and_extract,
            request.video_url,
            request.format,
            request.quality,
            None,  # Sin callback de progreso
        )
        
        # 4. Subir a Supabase
        audio_url = await asyncio.to_thread(storage.upload_file, audio_file)
        
        # 5. Obtener tamaño
        file_size = audio_file.stat().st_size
        file_size_formatted = video.format_file_size(file_size)
        
        # 6. Limpiar archivo temporal
        video.cleanup_file(audio_file)
        
        # 7. Calcular tiempo de procesamiento
        processing_time = round(time.time() - start_time, 2)
        
        # 8. Registrar log de éxito (API)
        logs.add_log(
            source=ExecutionSource.API,
            video_url=request.video_url,
            status="success",
            video_title=video_info.title,
            audio_url=audio_url,
            file_size_formatted=file_size_formatted,
            duration_formatted=video_info.duration_formatted,
            format=request.format.value,
            quality=request.quality.value,
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
        
    except ValueError as e:
        processing_time = round(time.time() - start_time, 2)
        # Registrar log de error (API)
        logs.add_log(
            source=ExecutionSource.API,
            video_url=request.video_url,
            status="error",
            error_code="VALIDATION_ERROR",
            error_message=str(e),
            processing_time=processing_time,
        )
        return ProcessResponse(
            status="error",
            error_code="VALIDATION_ERROR",
            message=str(e),
            processing_time=processing_time,
        )
    except FileNotFoundError as e:
        processing_time = round(time.time() - start_time, 2)
        logs.add_log(
            source=ExecutionSource.API,
            video_url=request.video_url,
            status="error",
            error_code="EXTRACTION_FAILED",
            error_message=str(e),
            processing_time=processing_time,
        )
        return ProcessResponse(
            status="error",
            error_code="EXTRACTION_FAILED",
            message=str(e),
            processing_time=processing_time,
        )
    except Exception as e:
        processing_time = round(time.time() - start_time, 2)
        logs.add_log(
            source=ExecutionSource.API,
            video_url=request.video_url,
            status="error",
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


@router.post("/process-video", response_model=ProcessResponse)
async def process_video_alt(request: ProcessRequest):
    """
    Alias de /process para compatibilidad con documentación técnica.
    Mismo funcionamiento que POST /process
    """
    return await process_video(request)


# ============== Extraction ==============

@router.post("/extract", response_model=JobResponse)
async def start_extraction(request: ExtractRequest, background_tasks: BackgroundTasks):
    """
    Inicia la extracción de audio de un video
    
    Retorna un job_id para consultar el estado con GET /jobs/{job_id}
    """
    if not storage.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Supabase no está configurado. Define SUPABASE_URL y SUPABASE_KEY"
        )
    
    # Crear job
    job = jobs.create_job()
    
    # Procesar en background
    background_tasks.add_task(jobs.process_job, job.job_id, request)
    
    return job


# ============== Jobs ==============

@router.get("/jobs", response_model=list[JobResponse])
async def list_jobs():
    """Lista todos los jobs"""
    return jobs.get_all_jobs()


@router.get("/jobs/stats", response_model=StatsResponse)
async def get_job_stats():
    """Obtiene estadísticas de jobs"""
    stats = jobs.get_stats()
    return StatsResponse(**stats)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """
    Obtiene el estado de un job de extracción
    
    - **job_id**: ID del job retornado por POST /extract
    """
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


# ============== Maintenance ==============

@router.post("/cleanup")
async def cleanup():
    """Limpia archivos y jobs antiguos"""
    files_cleaned = video.cleanup_old_files()
    jobs_cleaned = jobs.cleanup_old_jobs()
    
    return {
        "files_cleaned": files_cleaned,
        "jobs_cleaned": jobs_cleaned,
    }


# ============== Execution Logs ==============

@router.get("/logs", response_model=LogsResponse)
async def get_all_logs(limit: int = 50):
    """Obtiene todos los logs de ejecución"""
    all_logs = logs.get_all_logs(limit)
    return LogsResponse(total=len(all_logs), logs=all_logs)


@router.get("/logs/api", response_model=LogsResponse)
async def get_api_logs(limit: int = 50):
    """Obtiene logs de ejecuciones vía API"""
    api_logs = logs.get_api_logs(limit)
    return LogsResponse(total=len(api_logs), logs=api_logs)


@router.get("/logs/web", response_model=LogsResponse)
async def get_web_logs(limit: int = 50):
    """Obtiene logs de ejecuciones vía Web App"""
    web_logs = logs.get_web_logs(limit)
    return LogsResponse(total=len(web_logs), logs=web_logs)


@router.get("/logs/errors", response_model=LogsResponse)
async def get_error_logs(limit: int = 50):
    """Obtiene solo logs con errores"""
    error_logs = logs.get_error_logs(limit)
    return LogsResponse(total=len(error_logs), logs=error_logs)


@router.get("/logs/stats")
async def get_logs_stats():
    """Obtiene estadísticas de ejecuciones"""
    return logs.get_stats()


@router.delete("/logs")
async def clear_all_logs():
    """Limpia todos los logs"""
    count = logs.clear_logs()
    return {"message": f"Se eliminaron {count} logs"}
