"""
Video to Audio API
Microservicio para extraer audio de videos de YouTube/Vimeo
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routes import router
from .services import video


TEMP_DIR = Path("/tmp/video-to-audio")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle de la aplicación"""
    # Startup
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    print("🚀 Video to Audio API iniciada")
    
    yield
    
    # Shutdown
    video.cleanup_old_files(max_age_hours=0)  # Limpiar todo
    print("👋 Video to Audio API detenida")


def create_app() -> FastAPI:
    """Factory de la aplicación"""
    settings = get_settings()
    
    app = FastAPI(
        title="Video to Audio API",
        description="Extrae audio de videos de YouTube/Vimeo y los sube a Supabase",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Rutas
    app.include_router(router, prefix="/api")
    
    @app.get("/")
    async def root():
        return {
            "name": "Video to Audio API",
            "version": "1.0.0",
            "docs": "/docs",
        }
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
