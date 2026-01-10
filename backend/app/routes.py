@router.post("/upload/streaming", response_model=JobResponse)
async def upload_streaming(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    format: str = Form("mp3"),
    quality: str = Form("192"),
):
    """
    Upload con streaming - Retorna job_id INMEDIATAMENTE sin esperar el archivo completo. 
    El archivo se procesa en background mientras se va recibiendo.
    """
    if not storage.is_configured():
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    
    # Validar formato
    if not file.filename or not upload. is_valid_video_file(file.filename):
        raise HTTPException(status_code=400, detail="Formato no soportado")
    
    # Validar parámetros
    try:
        audio_format = AudioFormat(format. lower())
    except ValueError:
        audio_format = AudioFormat.MP3
    
    try: 
        audio_quality = AudioQuality(quality)
    except ValueError:
        audio_quality = AudioQuality. MEDIUM
    
    # 1. Crear job INMEDIATAMENTE
    job = jobs.create_job(
        video_url=f"upload://{file.filename}",
        format=audio_format. value,
        quality=audio_quality.value,
        source="upload-streaming"
    )
    
    # 2. Procesar en background (recibir archivo + procesar)
    background_tasks.add_task(
        _receive_and_process_file,
        job. job_id,
        file,
        file.filename,
        audio_format,
        audio_quality,
    )
    
    # 3.  RETORNAR JOB_ID INMEDIATAMENTE (sin esperar el archivo)
    return job


async def _receive_and_process_file(
    job_id: str,
    file: UploadFile,
    filename: str,
    audio_format: AudioFormat,
    audio_quality: AudioQuality,
):
    """Recibe el archivo y lo procesa - corre en background"""
    temp_video_path = None
    audio_file = None
    start_time = time.time()
    
    try:
        # 1. Recibir archivo
        jobs.update_job(job_id, status="processing", progress=5, stage="Recibiendo archivo...")
        
        suffix = Path(filename).suffix
        temp_video_path = Path(tempfile.mktemp(suffix=suffix))
        
        chunk_size = 8 * 1024 * 1024  # 8MB
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
                    jobs.update_job(job_id, progress=progress, stage=f"Recibiendo...  ({upload.format_file_size(total_written)})")
        
        video_size = temp_video_path.stat().st_size
        video_size_formatted = upload.format_file_size(video_size)
        
        # Validar tamaño
        settings = get_settings()
        max_size_bytes = settings.max_file_size_mb * 1024 * 1024
        if video_size > max_size_bytes:
            raise ValueError(f"Archivo muy grande ({video_size_formatted}). Máximo: {settings.max_file_size_mb}MB")
        
        # 2. Procesar (usar la función existente)
        jobs.update_job(job_id, progress=15, video_title=filename)
        
        # Continuar con el procesamiento normal
        await jobs.process_upload_job(
            job_id,
            temp_video_path,
            filename,
            audio_format,
            audio_quality,
        )
        
    except Exception as e:
        processing_time = round(time.time() - start_time, 2)
        
        if temp_video_path and temp_video_path.exists():
            upload.cleanup_file(temp_video_path)
        if audio_file and audio_file. exists():
            upload.cleanup_file(audio_file)
        
        jobs.update_job(
            job_id,
            status="failed",
            error_code="STREAMING_UPLOAD_FAILED",
            error_message=str(e),
            processing_time=processing_time,
        )
