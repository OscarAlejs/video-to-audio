"""
Servicio de base de datos - Jobs en Supabase
"""
from datetime import datetime
from typing import Optional
from uuid import uuid4

from .storage import get_supabase_client


def create_job(
    video_url: str,
    format: str = "mp3",
    quality: str = "192",
    source: str = "api"
) -> dict:
    """Crea un nuevo job en Supabase"""
    client = get_supabase_client()
    
    job_id = str(uuid4())
    
    data = {
        "id": job_id,
        "status": "pending",
        "progress": 0,
        "stage": "iniciando",
        "video_url": video_url,
        "format": format,
        "quality": quality,
        "source": source,
    }
    
    result = client.table("jobs").insert(data).execute()
    
    return result.data[0] if result.data else data


def get_job(job_id: str) -> Optional[dict]:
    """Obtiene un job por ID"""
    client = get_supabase_client()
    
    result = client.table("jobs").select("*").eq("id", job_id).execute()
    
    return result.data[0] if result.data else None


def update_job(job_id: str, **kwargs) -> Optional[dict]:
    """Actualiza un job"""
    client = get_supabase_client()
    
    kwargs["updated_at"] = datetime.now().isoformat()
    
    result = client.table("jobs").update(kwargs).eq("id", job_id).execute()
    
    return result.data[0] if result.data else None


def list_jobs(
    status: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 50
) -> list[dict]:
    """Lista jobs con filtros opcionales"""
    client = get_supabase_client()
    
    query = client.table("jobs").select("*").order("created_at", desc=True).limit(limit)
    
    if status:
        query = query.eq("status", status)
    if source:
        query = query.eq("source", source)
    
    result = query.execute()
    
    return result.data or []


def get_jobs_stats() -> dict:
    """Obtiene estadísticas de jobs"""
    client = get_supabase_client()
    
    all_jobs = client.table("jobs").select("status, source").execute()
    jobs = all_jobs.data or []
    
    return {
        "total": len(jobs),
        "pending": sum(1 for j in jobs if j["status"] == "pending"),
        "processing": sum(1 for j in jobs if j["status"] in ["processing", "downloading", "extracting", "uploading"]),
        "completed": sum(1 for j in jobs if j["status"] == "completed"),
        "failed": sum(1 for j in jobs if j["status"] == "failed"),
        "api_total": sum(1 for j in jobs if j["source"] == "api"),
        "web_total": sum(1 for j in jobs if j["source"] == "web"),
    }


def delete_job(job_id: str) -> bool:
    """Elimina un job"""
    client = get_supabase_client()
    
    result = client.table("jobs").delete().eq("id", job_id).execute()
    
    return len(result.data) > 0 if result.data else False


def cleanup_old_jobs(hours: int = 24) -> int:
    """Elimina jobs completados/fallidos más antiguos que X horas"""
    client = get_supabase_client()
    
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    
    result = client.table("jobs").delete().lt("created_at", cutoff).in_("status", ["completed", "failed"]).execute()
    
    return len(result.data) if result.data else 0
