"""
Servicio de almacenamiento en Supabase con soporte para archivos grandes (TUS)
"""
import re
import base64
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
from pathlib import Path
from typing import Optional
from supabase import create_client, Client
from ..config import get_settings

_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """Obtiene cliente de Supabase (singleton)"""
    global _client
    
    if _client is None:
        settings = get_settings()
        
        if not settings.supabase_url or not settings.supabase_key:
            raise ValueError(
                "Supabase no configurado. "
                "Define SUPABASE_URL y SUPABASE_KEY en las variables de entorno."
            )
        
        _client = create_client(settings.supabase_url, settings.supabase_key)
    
    return _client


def sanitize_filename(filename: str) -> str:
    """Elimina caracteres no permitidos del nombre de archivo"""
    sanitized = re.sub(r'[^a-zA-Z0-9_\-.]', '_', filename)
    sanitized = re.sub(r'_+', '_', sanitized)
    return sanitized.strip('_')[:80]


def _b64encode(s: str) -> str:
    """Encode string to base64 for TUS metadata"""
    return base64.b64encode(s.encode()).decode()


def _create_http_session() -> requests.Session:
    """Crea sesión HTTP optimizada para uploads grandes"""
    session = requests.Session()
    
    # Configurar reintentos
    retry_strategy = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "PATCH"],
    )
    
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=1,
        pool_maxsize=1,
    )
    
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    
    return session


def upload_file(file_path: Path, folder: str = "audio") -> str:
    """
    Sube archivo a Supabase Storage.
    Usa TUS (resumable) para archivos > 4MB, upload directo para menores.
    """
    file_size = file_path.stat().st_size
    
    # Usar TUS para archivos > 4MB
    if file_size > 4 * 1024 * 1024:
        return upload_file_tus(file_path, folder)
    else:
        return upload_file_direct(file_path, folder)


def upload_file_direct(file_path: Path, folder: str = "audio") -> str:
    """Upload directo para archivos pequeños (< 4MB)"""
    settings = get_settings()
    client = get_supabase_client()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = sanitize_filename(file_path.name)
    storage_path = f"{folder}/{timestamp}_{safe_name}"
    
    extension = file_path.suffix.lower()[1:]
    content_types = {
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
        "wav": "audio/wav",
        "opus": "audio/opus",
    }
    content_type = content_types.get(extension, "audio/mpeg")
    
    with open(file_path, "rb") as f:
        file_data = f.read()
    
    client.storage.from_(settings.supabase_bucket).upload(
        path=storage_path,
        file=file_data,
        file_options={"content-type": content_type}
    )
    
    public_url = client.storage.from_(settings.supabase_bucket).get_public_url(storage_path)
    
    return public_url


def upload_file_tus(file_path: Path, folder: str = "audio", max_retries: int = 5) -> str:
    """
    Upload resumible (TUS) para archivos grandes (> 4MB).
    Sube en chunks de 3MB con reintentos automáticos.
    """
    settings = get_settings()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = sanitize_filename(file_path.name)
    storage_path = f"{folder}/{timestamp}_{safe_name}"
    
    file_size = file_path.stat().st_size
    
    # Detectar content type
    extension = file_path.suffix.lower()[1:]
    content_types = {
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
        "wav": "audio/wav",
        "opus": "audio/opus",
    }
    content_type = content_types.get(extension, "audio/mpeg")
    
    # Crear sesión HTTP
    session = _create_http_session()
    
    # Paso 1: Crear upload session
    tus_url = f"{settings.supabase_url}/storage/v1/upload/resumable"
    
    headers = {
        "Authorization": f"Bearer {settings.supabase_key}",
        "x-upsert": "true",
        "Upload-Length": str(file_size),
        "Upload-Metadata": f"bucketName {_b64encode(settings.supabase_bucket)},objectName {_b64encode(storage_path)},contentType {_b64encode(content_type)}",
        "Tus-Resumable": "1.0.0",
    }
    
    for attempt in range(max_retries):
        try:
            response = session.post(tus_url, headers=headers, timeout=30)
            
            if response.status_code == 201:
                break
            elif response.status_code == 413:
                raise Exception(f"Archivo muy grande para Supabase. Verifica el límite del bucket. Status: {response.status_code}")
            else:
                raise Exception(f"Error creando upload TUS: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise Exception(f"Error de conexión creando upload TUS: {str(e)}")
    
    upload_url = response.headers.get("Location")
    if not upload_url:
        raise Exception("No se recibió Location header de TUS")
    
    # Paso 2: Subir en chunks de 3MB (más pequeños para evitar timeouts)
    chunk_size = 3 * 1024 * 1024  # 3MB
    offset = 0
    
    with open(file_path, "rb") as f:
        while offset < file_size:
            f.seek(offset)
            chunk = f.read(chunk_size)
            chunk_len = len(chunk)
            
            # Reintentos para cada chunk
            chunk_uploaded = False
            for attempt in range(max_retries):
                try:
                    patch_headers = {
                        "Authorization": f"Bearer {settings.supabase_key}",
                        "Upload-Offset": str(offset),
                        "Content-Type": "application/offset+octet-stream",
                        "Content-Length": str(chunk_len),
                        "Tus-Resumable": "1.0.0",
                    }
                    
                    patch_response = session.patch(
                        upload_url,
                        headers=patch_headers,
                        data=chunk,
                        timeout=120  # 2 minutos por chunk
                    )
                    
                    if patch_response.status_code in [200, 204]:
                        # Éxito - actualizar offset
                        new_offset = patch_response.headers.get("Upload-Offset")
                        if new_offset:
                            offset = int(new_offset)
                        else:
                            offset += chunk_len
                        chunk_uploaded = True
                        break
                    else:
                        raise Exception(f"Status {patch_response.status_code}: {patch_response.text}")
                        
                except (requests.exceptions.RequestException, Exception) as e:
                    if attempt < max_retries - 1:
                        wait_time = min(2 ** attempt, 30)
                        time.sleep(wait_time)
                        
                        # Recuperar offset del servidor
                        try:
                            head_response = session.head(
                                upload_url,
                                headers={
                                    "Authorization": f"Bearer {settings.supabase_key}",
                                    "Tus-Resumable": "1.0.0",
                                },
                                timeout=15
                            )
                            if head_response.status_code == 200:
                                server_offset = head_response.headers.get("Upload-Offset")
                                if server_offset:
                                    offset = int(server_offset)
                                    f.seek(offset)
                        except:
                            pass
                        continue
                    else:
                        raise Exception(f"Error subiendo chunk offset {offset} después de {max_retries} intentos: {str(e)}")
            
            if not chunk_uploaded:
                raise Exception(f"No se pudo subir chunk en offset {offset}")
    
    session.close()
    
    # Construir URL pública
    public_url = f"{settings.supabase_url}/storage/v1/object/public/{settings.supabase_bucket}/{storage_path}"
    return public_url


def delete_file(storage_path: str) -> bool:
    """Elimina archivo del storage"""
    settings = get_settings()
    client = get_supabase_client()
    
    try:
        client.storage.from_(settings.supabase_bucket).remove([storage_path])
        return True
    except Exception:
        return False


def is_configured() -> bool:
    """Verifica si Supabase está configurado"""
    settings = get_settings()
    return bool(settings.supabase_url and settings.supabase_key)
