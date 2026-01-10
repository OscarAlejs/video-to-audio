"""
Configuración del Backend
"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "Video to Audio API"
    debug: bool = False
    
    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_bucket: str = "audio-files"
    
    # Limits
    max_duration_minutes: int = 60
    max_file_size_mb: int = 1024  # 1GB = 1024MB
    
    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
