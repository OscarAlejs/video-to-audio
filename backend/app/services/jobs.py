"""
Servicio de gestión de trabajos de extracción
"""
import asyncio
import time
from datetime import datetime

from pathlib import Path

from ..models import (
    AudioFormat,
    AudioQuality,
    ExtractRequest,
    ExtractResult,
    JobResponse,
    JobStatus,
    VideoInfo,
)
from . import video, storage, db, upload


def create_job(video_url:  str, format: str, quality: str, source: str = "web") -> JobResponse:
    """Crea un nuevo job en Supabase"""
    job_data = db.create_job(
        video_url=video_url,
        format=format,
        quality=quality,
        source=source
    )
    
    return JobResponse(
        job_id=job_data["id"],
        status=JobStatus. PENDING,
        progress=0,
        message="Iniciando.. .",
        created_at=datetime.fromisoformat(job_data["created_at"]. replace("Z", "+00:00")) if isinstance(job_data["created_at"], str) else job_data["created_at"],
    )


def get_job(job_id: str) -> JobResponse | None:
    """Obtiene un job de Supabase"""
    job_data = db.get_job(job_id)
    
    if not job_data: 
        return None
    
    # ✅ CAMBIO:  Construir video_info solo si hay datos válidos
    video_info = None
    # Verificar que al menos tengamos id y source (campos requeridos antes)
    if job_data.get("video_id") or job_data.get("video_title"):
        video_info = VideoInfo(
            id=job_data. get("video_id"),  # Puede ser None ahora
            title=job_data.get("video_title"),
            duration_seconds=job_data.get("video_duration"),
            duration_formatted=video.format_duration(job_data.get("video_duration")) if job_data.get("video_duration") else None,
            thumbnail=job_data.get("video_thumbnail"),
            source=job_data.get("video_source"),  # Puede ser None ahora
            channel=job_data.get("video_channel"),
        )
    
    # Construir result si completado o fallido
    result = None
    if job_data["status"] == "completed" and job_data. get("audio_url"):
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
        created_at = datetime.fromisoformat(created_at. replace("Z", "+00:00"))
    
    return JobResponse(
        job_id=job_data["id"],
        status=JobStatus(job_data["status"]),
        progress=job_data.get("progress", 0),
        message=job_data.get("stage", ""),
        created_at=created_at,
        video_info=video_info,  # Puede ser None ahora
        result=result,
    )


def update_job(job_id: str, **kwargs) -> None:
    """Actualiza un job en Supabase"""
    db.update_job(job_id, **kwargs)


def delete_job(job_id: str) -> bool:
    """Elimina un job"""
    return db.delete_job(job_id)


def get_all_jobs(limit: int = 50) -> list[JobResponse]:
    """
    Obtiene todos los jobs
    ✅ CAMBIO:  Manejo de errores para jobs con datos incompletos
    """
    jobs_data = db.list_jobs(limit=limit)
    result = []
    
    for j in jobs_data:
        try:
            job = get_job(j["id"])
            if job:
                result.append(job)
        except Exception as e:
            # Log error pero continuar con los demás jobs
            print(f"⚠️ Error al obtener job {j. get('id', 'unknown')}: {e}")
            continue
    
    return result


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
        print(f"🚀 Iniciando job {job_id[:8]} - URL: {request.url}")
        
        # 1. Obtener info del video
        update_job(job_id, status="processing", progress=5, stage="Obteniendo información del video...")
        
        info = await asyncio.to_thread(video.get_video_info, request.url)
        print(f"📊 Video: {info.title} ({info.duration_formatted})")
        
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
        print(f"✅ Job {job_id[:8]} completado en {processing_time}s")
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
        print(f"❌ Job {job_id[:8]} falló después de {processing_time}s: {str(e)}")
        
        update_job(
            job_id,
            status="failed",
            progress=0,
            stage="Error",
            error_code="EXTRACTION_FAILED",
            error_message=str(e),
            processing_time=processing_time,
        )


async def process_upload_job(
    job_id: str,
    video_file_path: Path,
    filename: str,
    audio_format: AudioFormat,
    audio_quality: AudioQuality,
) -> None:
    """
    Procesa un job de upload de forma asíncrona
    Similar a process_job pero para archivos subidos
    """
    start_time = time.time()
    temp_video_path = video_file_path
    audio_file = None
    
    try:
        print(f"📤 Procesando upload job {job_id[:8]} - Archivo: {filename}")
        
        # 1. Validar archivo
        update_job(job_id, status="processing", progress=5, stage="Validando archivo...")
        
        if not temp_video_path.exists():
            raise FileNotFoundError("Archivo temporal no encontrado")
        
        # 2. Obtener información del video
        update_job(job_id, status="processing", progress=10, stage="Analizando video...")
        
        duration = await asyncio.to_thread(upload.get_video_duration, temp_video_path)
        duration_formatted = video.format_duration(duration) if duration else "Desconocida"
        
        video_size = temp_video_path.stat().st_size
        video_size_formatted = upload.format_file_size(video_size)
        
        # Guardar info del video
        update_job(
            job_id,
            progress=15,
            video_title=filename,
            video_duration=duration,
        )
        
        # Validar duración
        from ..config import get_settings
        settings = get_settings()
        if duration and duration > settings.max_duration_minutes * 60:
            raise ValueError(
                f"Video muy largo ({duration // 60} min). "
                f"Máximo permitido: {settings.max_duration_minutes} min"
            )
        
        # Validar tamaño
        max_size_bytes = settings.max_file_size_mb * 1024 * 1024
        if video_size > max_size_bytes:
            raise ValueError(
                f"Archivo muy grande ({video_size_formatted}). "
                f"Máximo permitido: {settings.max_file_size_mb}MB"
            )
        
        # 3. Extraer audio
        update_job(job_id, status="extracting", progress=20, stage="Extrayendo audio...")
        
        audio_file = await asyncio.to_thread(
            upload.extract_audio_from_file,
            temp_video_path,
            audio_format,
            audio_quality,
        )
        
        # 4. Subir a Supabase
        update_job(job_id, status="uploading", progress=85, stage="Subiendo a la nube...")
        
        audio_url = await asyncio.to_thread(storage.upload_file, audio_file)
        
        # 5. Obtener tamaño del archivo de audio
        file_size = audio_file.stat().st_size
        file_size_formatted = upload.format_file_size(file_size)
        
        # 6. Limpiar archivos temporales
        upload.cleanup_file(temp_video_path)
        upload.cleanup_file(audio_file)
        
        # 7. Calcular tiempo de procesamiento
        processing_time = round(time.time() - start_time, 2)
        
        # 8. Completar job
        print(f"✅ Upload job {job_id[:8]} completado en {processing_time}s - {file_size_formatted}")
        update_job(
            job_id,
            status="completed",
            progress=100,
            stage="¡Audio extraído exitosamente!",
            audio_url=audio_url,
            file_size=file_size_formatted,
            processing_time=processing_time,
        )
        
    except Exception as e: 
        processing_time = round(time.time() - start_time, 2)
        print(f"❌ Upload job {job_id[:8]} falló: {str(e)}")
        
        # Limpiar archivos temporales en caso de error
        if temp_video_path and temp_video_path.exists():
            upload.cleanup_file(temp_video_path)
        if audio_file and audio_file.exists():
            upload.cleanup_file(audio_file)
        
        update_job(
            job_id,
            status="failed",
            progress=0,
            stage="Error",
            error_code="UPLOAD_EXTRACTION_FAILED",
            error_message=str(e),
            processing_time=processing_time,
        )
