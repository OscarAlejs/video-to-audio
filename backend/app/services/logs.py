"""
Servicio de logs de ejecución
"""
from datetime import datetime
from typing import Optional
from uuid import uuid4

from ..models import ExecutionLog, ExecutionSource


# Almacén en memoria de logs (en producción usar base de datos)
_logs: list[ExecutionLog] = []
MAX_LOGS = 100  # Máximo de logs a mantener


def add_log(
    source: ExecutionSource,
    video_url: str,
    status: str,
    video_title: Optional[str] = None,
    audio_url: Optional[str] = None,
    file_size_formatted: Optional[str] = None,
    duration_formatted: Optional[str] = None,
    format: Optional[str] = None,
    quality: Optional[str] = None,
    processing_time: Optional[float] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> ExecutionLog:
    """Agrega un nuevo log de ejecución"""
    log = ExecutionLog(
        id=str(uuid4())[:8],
        source=source,
        timestamp=datetime.now(),
        video_url=video_url,
        video_title=video_title,
        status=status,
        audio_url=audio_url,
        file_size_formatted=file_size_formatted,
        duration_formatted=duration_formatted,
        format=format,
        quality=quality,
        processing_time=processing_time,
        error_code=error_code,
        error_message=error_message,
    )
    
    _logs.insert(0, log)  # Insertar al inicio (más reciente primero)
    
    # Limitar cantidad de logs
    if len(_logs) > MAX_LOGS:
        _logs.pop()
    
    return log


def get_all_logs(limit: int = 50) -> list[ExecutionLog]:
    """Obtiene todos los logs"""
    return _logs[:limit]


def get_logs_by_source(source: ExecutionSource, limit: int = 50) -> list[ExecutionLog]:
    """Obtiene logs filtrados por origen"""
    filtered = [log for log in _logs if log.source == source]
    return filtered[:limit]


def get_api_logs(limit: int = 50) -> list[ExecutionLog]:
    """Obtiene logs de ejecuciones vía API"""
    return get_logs_by_source(ExecutionSource.API, limit)


def get_web_logs(limit: int = 50) -> list[ExecutionLog]:
    """Obtiene logs de ejecuciones vía Web"""
    return get_logs_by_source(ExecutionSource.WEB, limit)


def get_error_logs(limit: int = 50) -> list[ExecutionLog]:
    """Obtiene solo logs con errores"""
    filtered = [log for log in _logs if log.status == "error"]
    return filtered[:limit]


def get_stats() -> dict:
    """Obtiene estadísticas de logs"""
    api_logs = [l for l in _logs if l.source == ExecutionSource.API]
    web_logs = [l for l in _logs if l.source == ExecutionSource.WEB]
    
    return {
        "total": len(_logs),
        "api_total": len(api_logs),
        "api_success": sum(1 for l in api_logs if l.status == "success"),
        "api_errors": sum(1 for l in api_logs if l.status == "error"),
        "web_total": len(web_logs),
        "web_success": sum(1 for l in web_logs if l.status == "success"),
        "web_errors": sum(1 for l in web_logs if l.status == "error"),
    }


def clear_logs() -> int:
    """Limpia todos los logs"""
    count = len(_logs)
    _logs.clear()
    return count
