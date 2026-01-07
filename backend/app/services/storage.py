"""
Servicio de almacenamiento en Supabase
"""
import re
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
    # Solo permitir: letras, números, guión, underscore, punto
    sanitized = re.sub(r'[^a-zA-Z0-9_\-.]', '_', filename)
    # Eliminar underscores múltiples
    sanitized = re.sub(r'_+', '_', sanitized)
    return sanitized.strip('_')


def upload_file(file_path: Path, folder: str = "audio") -> str:
    """
    Sube archivo a Supabase Storage
    
    Args:
        file_path: Path al archivo local
        folder: Carpeta destino en el bucket
    
    Returns:
        URL pública del archivo
    """
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
