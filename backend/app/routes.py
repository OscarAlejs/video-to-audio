"""
Rutas de la API
"""
import os
import time
import asyncio
import tempfile
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from .config import get_settings
from .models import (
    ExtractRequest,
    HealthResponse,
    JobResponse,
    ProcessRequest,
    ProcessResponse,
    StatsResponse,
    VideoInfo,
    AudioFormat,
    AudioQuality,
    UploadResponse,
)
from .services import jobs, storage, video, db, upload
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
    
    Soporta:
    - YouTube: https://youtube.com/watch?v=...
    - Vimeo: https://vimeo.com/...
    - URLs directas: https://example.com/video.mp4
    - Supabase Storage: https://[project].supabase.co/storage/v1/object/public/...
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
    **Modo API** - Procesa un video de forma síncrona.
    Guarda el job en Supabase para auditoría.
    
    Soporta:
    - YouTube/Vimeo
    - URLs directas de archivos de video (.mp4, .mkv, .webm, etc.)
    - Supabase Storage
    """
    start_time = time.time()
    settings = get_settings()
    
    print(f"🎬 Procesando video: {request.video_url}")
    
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
        
        print(f"✅ Video procesado en {processing_time}s")
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
        print(f"❌ Error procesando: {str(e)}")
        
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


# ============== API Mode - Download Direct ==============

@router.post("/process/download")
async def process_and_download(request: ProcessRequest):
    """
    **Modo API** - Procesa y devuelve el archivo de audio directamente.
    Ideal para n8n cuando necesitas el binario del audio.
    """
    start_time = time.time()
    settings = get_settings()
    
    if not storage.is_configured():
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    
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
            raise HTTPException(
                status_code=400,
                detail=f"Video muy largo ({video_info.duration_seconds // 60} min). Máximo: {settings.max_duration_minutes} min"
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
        
        # 4. Leer el archivo en memoria
        db.update_job(job_id, status="uploading", progress=70, stage="Preparando...")
        
        with open(audio_file, "rb") as f:
            audio_data = f.read()
        
        file_size = len(audio_data)
        file_size_formatted = video.format_file_size(file_size)
        filename = os.path.basename(str(audio_file))
        
        # 5. Subir a Supabase (backup)
        db.update_job(job_id, progress=85, stage="Subiendo backup...")
        audio_url = await asyncio.to_thread(storage.upload_file, audio_file)
        
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
        
        # 9. Determinar content type
        content_types = {
            "mp3": "audio/mpeg",
            "m4a": "audio/mp4",
            "wav": "audio/wav",
            "opus": "audio/opus"
        }
        content_type = content_types.get(request.format.value, "audio/mpeg")
        
        # 10. Devolver archivo directamente
        return StreamingResponse(
            iter([audio_data]),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(file_size),
                "X-Audio-URL": audio_url,
                "X-Job-ID": job_id,
                "X-Video-Title": video_info.title[:100] if video_info.title else "",
                "X-Processing-Time": str(processing_time),
                "X-File-Size": file_size_formatted,
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        processing_time = round(time.time() - start_time, 2)
        
        db.update_job(
            job_id,
            status="failed",
            error_code="INTERNAL_ERROR",
            error_message=str(e),
            processing_time=processing_time,
        )
        
        raise HTTPException(status_code=500, detail=str(e))


# ============== File Upload ==============

@router.post("/upload", response_model=UploadResponse)
async def upload_video_file(
    file: UploadFile = File(...),
    format: str = Form("mp3"),
    quality: str = Form("192"),
):
    """
    **Upload de archivo** - Sube un archivo de video y extrae el audio.
    
    - **file**: Archivo de video (mp4, mkv, webm, avi, mov, etc.)
    - **format**: Formato de salida (mp3, m4a, wav, opus)
    - **quality**: Calidad en kbps (128, 192, 256, 320)
    
    Nota: Este endpoint procesa el archivo de forma síncrona y puede tardar varios minutos.
    Para archivos grandes, considera usar el endpoint asíncrono /extract.
    """
    start_time = time.time()
    
    print(f"📤 Upload iniciado: {file.filename} ({file.size / 1024 / 1024:.1f}MB)" if file.size else f"📤 Upload iniciado: {file.filename}")
    
    if not storage.is_configured():
        return UploadResponse(
            status="error",
            error_code="SUPABASE_NOT_CONFIGURED",
            message="Supabase no está configurado"
        )
    
    # Validar formato de archivo
    if not file.filename or not upload.is_valid_video_file(file.filename):
        return UploadResponse(
            status="error",
            error_code="INVALID_FILE_FORMAT",
            message="Formato de archivo no soportado. Usa: mp4, mkv, webm, avi, mov, flv, wmv"
        )
    
    # Validar parámetros
    try:
        audio_format = AudioFormat(format.lower())
    except ValueError:
        audio_format = AudioFormat.MP3
    
    try:
        audio_quality = AudioQuality(quality)
    except ValueError:
        audio_quality = AudioQuality.MEDIUM
    
    # Crear job
    job_data = db.create_job(
        video_url=f"upload://{file.filename}",
        format=audio_format.value,
        quality=audio_quality.value,
        source="upload"
    )
    job_id = job_data["id"]
    
    temp_video_path = None
    audio_file = None
    
    try:
        # 1. Guardar archivo temporal
        db.update_job(job_id, status="processing", progress=10, stage="Recibiendo archivo...")
        
        # Crear archivo temporal
        suffix = Path(file.filename).suffix
        temp_video_path = Path(tempfile.mktemp(suffix=suffix))
        
        # Guardar archivo usando streaming para archivos grandes
        with open(temp_video_path, "wb") as temp_file:
            # Leer en chunks de 8MB para evitar problemas de memoria y timeouts
            while True:
                chunk = await file.read(8 * 1024 * 1024)  # 8MB chunks
                if not chunk:
                    break
                temp_file.write(chunk)
        
        video_size = temp_video_path.stat().st_size
        video_size_formatted = upload.format_file_size(video_size)
        
        # Validar tamaño del archivo
        settings = get_settings()
        max_size_bytes = settings.max_file_size_mb * 1024 * 1024
        if video_size > max_size_bytes:
            upload.cleanup_file(temp_video_path)
            db.update_job(
                job_id,
                status="failed",
                error_code="FILE_TOO_LARGE",
                error_message=f"Archivo muy grande ({video_size_formatted}). Máximo: {settings.max_file_size_mb}MB"
            )
            return UploadResponse(
                status="error",
                error_code="FILE_TOO_LARGE",
                message=f"Archivo muy grande ({video_size_formatted}). Máximo permitido: {settings.max_file_size_mb}MB",
                processing_time=round(time.time() - start_time, 2),
            )
        
        # Obtener duración
        duration = upload.get_video_duration(temp_video_path)
        duration_formatted = video.format_duration(duration) if duration else "Desconocida"
        
        db.update_job(
            job_id,
            video_title=file.filename,
            video_duration=duration,
        )
        
        # 2. Extraer audio
        db.update_job(job_id, status="extracting", progress=40, stage="Extrayendo audio...")
        
        audio_file = await asyncio.to_thread(
            upload.extract_audio_from_file,
            temp_video_path,
            audio_format,
            audio_quality,
        )
        
        # 3. Subir a Supabase
        db.update_job(job_id, status="uploading", progress=80, stage="Subiendo...")
        
        audio_url = await asyncio.to_thread(storage.upload_file, audio_file)
        
        # 4. Obtener info del audio
        file_size = audio_file.stat().st_size
        file_size_formatted = upload.format_file_size(file_size)
        
        # 5. Limpiar archivos temporales
        upload.cleanup_file(temp_video_path)
        upload.cleanup_file(audio_file)
        
        # 6. Calcular tiempo
        processing_time = round(time.time() - start_time, 2)
        
        # 7. Actualizar job
        db.update_job(
            job_id,
            status="completed",
            progress=100,
            stage="Completado",
            audio_url=audio_url,
            file_size=file_size_formatted,
            processing_time=processing_time,
        )
        
        print(f"✅ Upload procesado: {audio_url}")
        return UploadResponse(
            status="success",
            audio_url=audio_url,
            filename=file.filename,
            file_size=file_size,
            file_size_formatted=file_size_formatted,
            original_size=video_size,
            original_size_formatted=video_size_formatted,
            duration=duration,
            duration_formatted=duration_formatted,
            format=audio_format.value,
            quality=audio_quality.value,
            processing_time=processing_time,
            job_id=job_id,
            message="Audio extraído exitosamente",
        )
        
    except Exception as e:
        processing_time = round(time.time() - start_time, 2)
        print(f"❌ Error en upload: {str(e)}")
        
        # Limpiar archivos temporales
        if temp_video_path:
            upload.cleanup_file(temp_video_path)
        if audio_file:
            upload.cleanup_file(audio_file)
        
        db.update_job(
            job_id,
            status="failed",
            error_code="EXTRACTION_FAILED",
            error_message=str(e),
            processing_time=processing_time,
        )
        
        return UploadResponse(
            status="error",
            error_code="EXTRACTION_FAILED",
            message=str(e),
            processing_time=processing_time,
        )


@router.post("/upload/download")
async def upload_and_download(
    file: UploadFile = File(...),
    format: str = Form("mp3"),
    quality: str = Form("192"),
):
    """
    **Upload + Download directo** - Sube un video y devuelve el audio directamente.
    Ideal para n8n y automatizaciones que necesitan el binario.
    """
    start_time = time.time()
    
    if not storage.is_configured():
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    
    # Validar formato de archivo
    if not file.filename or not upload.is_valid_video_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail="Formato de archivo no soportado. Usa: mp4, mkv, webm, avi, mov, flv, wmv"
        )
    
    # Validar parámetros
    try:
        audio_format = AudioFormat(format.lower())
    except ValueError:
        audio_format = AudioFormat.MP3
    
    try:
        audio_quality = AudioQuality(quality)
    except ValueError:
        audio_quality = AudioQuality.MEDIUM
    
    temp_video_path = None
    audio_file = None
    
    try:
        # 1. Guardar archivo temporal usando streaming
        suffix = Path(file.filename).suffix
        temp_video_path = Path(tempfile.mktemp(suffix=suffix))
        
        # Guardar archivo usando streaming para archivos grandes
        with open(temp_video_path, "wb") as temp_file:
            # Leer en chunks de 8MB para evitar problemas de memoria y timeouts
            while True:
                chunk = await file.read(8 * 1024 * 1024)  # 8MB chunks
                if not chunk:
                    break
                temp_file.write(chunk)
        
        # Validar tamaño del archivo
        settings = get_settings()
        video_size = temp_video_path.stat().st_size
        max_size_bytes = settings.max_file_size_mb * 1024 * 1024
        if video_size > max_size_bytes:
            upload.cleanup_file(temp_video_path)
            video_size_formatted = upload.format_file_size(video_size)
            raise HTTPException(
                status_code=413,
                detail=f"Archivo muy grande ({video_size_formatted}). Máximo permitido: {settings.max_file_size_mb}MB"
            )
        
        # 2. Extraer audio
        audio_file = await asyncio.to_thread(
            upload.extract_audio_from_file,
            temp_video_path,
            audio_format,
            audio_quality,
        )
        
        # 3. Leer audio en memoria
        with open(audio_file, "rb") as f:
            audio_data = f.read()
        
        file_size = len(audio_data)
        file_size_formatted = upload.format_file_size(file_size)
        filename = f"{Path(file.filename).stem}.{audio_format.value}"
        
        # 4. Subir a Supabase (backup)
        audio_url = await asyncio.to_thread(storage.upload_file, audio_file)
        
        # 5. Limpiar archivos temporales
        upload.cleanup_file(temp_video_path)
        upload.cleanup_file(audio_file)
        
        # 6. Calcular tiempo
        processing_time = round(time.time() - start_time, 2)
        
        # 7. Determinar content type
        content_types = {
            "mp3": "audio/mpeg",
            "m4a": "audio/mp4",
            "wav": "audio/wav",
            "opus": "audio/opus"
        }
        content_type = content_types.get(audio_format.value, "audio/mpeg")
        
        # 8. Devolver archivo directamente
        return StreamingResponse(
            iter([audio_data]),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(file_size),
                "X-Audio-URL": audio_url,
                "X-Original-Filename": file.filename,
                "X-Processing-Time": str(processing_time),
                "X-File-Size": file_size_formatted,
            }
        )
        
    except Exception as e:
        # Limpiar archivos temporales
        if temp_video_path:
            upload.cleanup_file(temp_video_path)
        if audio_file:
            upload.cleanup_file(audio_file)
        
        raise HTTPException(status_code=500, detail=str(e))


# ============== Upload (Async) ==============

@router.post("/upload/extract", response_model=JobResponse)
async def start_upload_extraction(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    format: str = Form("mp3"),
    quality: str = Form("192"),
):
    """
    **Upload asíncrono** - Sube un archivo de video y extrae el audio de forma asíncrona.
    Retorna job_id para consultar el progreso mediante polling.
    
    Ideal para archivos grandes que pueden causar timeouts.
    
    - **file**: Archivo de video (mp4, mkv, webm, avi, mov, etc.)
    - **format**: Formato de salida (mp3, m4a, wav, opus)
    - **quality**: Calidad en kbps (128, 192, 256, 320)
    
    **Uso:**
    1. Sube el archivo → obtienes job_id
    2. Poll a `/api/jobs/{job_id}` para ver el progreso
    3. Cuando status="completed", el audio_url estará disponible
    """
    if not storage.is_configured():
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    
    # Validar formato de archivo
    if not file.filename or not upload.is_valid_video_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail="Formato de archivo no soportado. Usa: mp4, mkv, webm, avi, mov, flv, wmv"
        )
    
    # Validar parámetros
    try:
        audio_format = AudioFormat(format.lower())
    except ValueError:
        audio_format = AudioFormat.MP3
    
    try:
        audio_quality = AudioQuality(quality)
    except ValueError:
        audio_quality = AudioQuality.MEDIUM
    
    # Crear job primero
    job = jobs.create_job(
        video_url=f"upload://{file.filename}",
        format=audio_format.value,
        quality=audio_quality.value,
        source="upload"
    )
    
    temp_video_path = None
    
    try:
        # 1. Guardar archivo temporal usando streaming
        # NOTA: Esta operación puede tardar para archivos grandes, pero es necesaria
        # Los timeouts de nginx deben ser lo suficientemente largos para permitir el upload
        jobs.update_job(job.job_id, status="processing", progress=5, stage="Recibiendo archivo...")
        
        # Crear archivo temporal
        suffix = Path(file.filename).suffix
        temp_video_path = Path(tempfile.mktemp(suffix=suffix))
        
        # Guardar archivo usando streaming para archivos grandes
        # Leer en chunks más pequeños para mejor progreso y evitar timeouts
        chunk_size = 2 * 1024 * 1024  # 2MB chunks (más pequeños para mejor progreso)
        total_written = 0
        
        with open(temp_video_path, "wb") as temp_file:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                temp_file.write(chunk)
                total_written += len(chunk)
                
                # Actualizar progreso cada 50MB recibidos
                if total_written % (50 * 1024 * 1024) < chunk_size:
                    progress = min(5 + int((total_written / (1024 * 1024 * 1024)) * 5), 10)  # 5-10%
                    jobs.update_job(job.job_id, progress=progress, stage=f"Recibiendo archivo... ({upload.format_file_size(total_written)})")
        
        video_size = temp_video_path.stat().st_size
        video_size_formatted = upload.format_file_size(video_size)
        
        # Validación básica de tamaño (rápida) - validación completa en background
        settings = get_settings()
        max_size_bytes = settings.max_file_size_mb * 1024 * 1024
        if video_size > max_size_bytes:
            upload.cleanup_file(temp_video_path)
            jobs.update_job(
                job.job_id,
                status="failed",
                error_code="FILE_TOO_LARGE",
                error_message=f"Archivo muy grande ({video_size_formatted}). Máximo: {settings.max_file_size_mb}MB"
            )
            raise HTTPException(
                status_code=413,
                detail=f"Archivo muy grande ({video_size_formatted}). Máximo permitido: {settings.max_file_size_mb}MB"
            )
        
        # Actualizar job con info básica del archivo
        jobs.update_job(
            job.job_id,
            progress=10,
            video_title=file.filename,
        )
        
        # 2. Iniciar procesamiento en background (validaciones y procesamiento completo)
        background_tasks.add_task(
            jobs.process_upload_job,
            job.job_id,
            temp_video_path,
            file.filename,
            audio_format,
            audio_quality,
        )
        
        # 3. Retornar job INMEDIATAMENTE después de recibir el archivo
        # El procesamiento continúa en background
        return job
        
    except HTTPException:
        # Re-lanzar HTTPException
        raise
    except Exception as e:
        # Limpiar archivo temporal si existe
        if temp_video_path and temp_video_path.exists():
            upload.cleanup_file(temp_video_path)
        
        # Marcar job como fallido
        jobs.update_job(
            job.job_id,
            status="failed",
            error_code="UPLOAD_FAILED",
            error_message=str(e),
        )
        
        raise HTTPException(status_code=500, detail=f"Error al procesar upload: {str(e)}")


# ============== Extraction (Async) ==============

@router.post("/extract", response_model=JobResponse)
async def start_extraction(request: ExtractRequest, background_tasks: BackgroundTasks):
    """
    Inicia extracción asíncrona - retorna job_id para polling
    
    Soporta:
    - YouTube/Vimeo
    - URLs directas de archivos de video (.mp4, .mkv, .webm, etc.)
    - Supabase Storage
    """
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


# ============== Upload Streaming (Sin timeout) ==============

@router.post("/upload/streaming", response_model=JobResponse)
async def upload_streaming(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    format: str = Form("mp3"),
    quality: str = Form("192"),
):
    """
    **Upload con streaming** - Retorna job_id INMEDIATAMENTE sin esperar el archivo completo.
    El archivo se recibe y procesa en background. 
    
    VENTAJA: No hay timeout porque el job_id se devuelve en <1 segundo. 
    """
    if not storage.is_configured():
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    
    # Validar formato de archivo
    if not file.filename or not upload. is_valid_video_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail="Formato de archivo no soportado. Usa:  mp4, mkv, webm, avi, mov, flv, wmv"
        )
    
    # Validar parámetros
    try:
        audio_format = AudioFormat(format.lower())
    except ValueError:
        audio_format = AudioFormat. MP3
    
    try:
        audio_quality = AudioQuality(quality)
    except ValueError:
        audio_quality = AudioQuality. MEDIUM
    
    # 1. Crear job INMEDIATAMENTE (esto tarda <1 segundo)
    job = jobs.create_job(
        video_url=f"upload://{file.filename}",
        format=audio_format. value,
        quality=audio_quality.value,
        source="upload-streaming"
    )
    
    # 2. Recibir y procesar en background
    background_tasks.add_task(
        _receive_and_process_file_streaming,
        job. job_id,
        file,
        file.filename,
        audio_format,
        audio_quality,
    )
    
    # 3. RETORNAR JOB INMEDIATAMENTE
    return job


async def _receive_and_process_file_streaming(
    job_id: str,
    file: UploadFile,
    filename: str,
    audio_format: AudioFormat,
    audio_quality: AudioQuality,
):
    """
    Recibe el archivo en background y lo procesa.
    Esta función corre de forma asíncrona, sin bloquear la respuesta HTTP.
    """
    temp_video_path = None
    audio_file = None
    start_time = time.time()
    
    try:
        # 1. Recibir archivo
        jobs.update_job(job_id, status="processing", progress=5, stage="Recibiendo archivo...")
        
        suffix = Path(filename).suffix
        temp_video_path = Path(tempfile.mktemp(suffix=suffix))
        
        chunk_size = 8 * 1024 * 1024  # 8MB chunks
        total_written = 0
        
        with open(temp_video_path, "wb") as temp_file:
            while True: 
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                temp_file.write(chunk)
                total_written += len(chunk)
                
                # Actualizar progreso cada 50MB
                if total_written % (50 * 1024 * 1024) < chunk_size:
                    progress = min(5 + int((total_written / (1024 * 1024 * 1024)) * 10), 15)
                    size_formatted = upload.format_file_size(total_written)
                    jobs.update_job(job_id, progress=progress, stage=f"Recibiendo...  ({size_formatted})")
        
        video_size = temp_video_path.stat().st_size
        video_size_formatted = upload.format_file_size(video_size)
        
        # Validar tamaño
        settings = get_settings()
        max_size_bytes = settings.max_file_size_mb * 1024 * 1024
        if video_size > max_size_bytes:
            raise ValueError(f"Archivo muy grande ({video_size_formatted}). Máximo: {settings.max_file_size_mb}MB")
        
        # 2. Actualizar job con info básica
        jobs.update_job(job_id, progress=15, video_title=filename)
        
        # 3. Procesar usando la función existente
        await jobs.process_upload_job(
            job_id,
            temp_video_path,
            filename,
            audio_format,
            audio_quality,
        )
        
    except Exception as e:
        processing_time = round(time.time() - start_time, 2)
        
        # Limpiar archivos temporales
        if temp_video_path and temp_video_path.exists():
            upload.cleanup_file(temp_video_path)
        if audio_file and audio_file.exists():
            upload. cleanup_file(audio_file)
        
        jobs.update_job(
            job_id,
            status="failed",
            error_code="STREAMING_UPLOAD_FAILED",
            error_message=str(e),
            processing_time=processing_time,
        )
