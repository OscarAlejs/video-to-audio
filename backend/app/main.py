"""
Video to Audio API
Microservicio para extraer audio de videos de YouTube/Vimeo
"""
import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.status import HTTP_504_GATEWAY_TIMEOUT

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
    
    # Middleware de timeout para peticiones largas
    @app.middleware("http")
    async def timeout_middleware(request: Request, call_next):
        try:
            start_time = time.time()
            # Tiempo límite en segundos (600 = 10 minutos)
            TIMEOUT_LIMIT = 600
            return await asyncio.wait_for(call_next(request), timeout=TIMEOUT_LIMIT)
        except asyncio.TimeoutError:
            process_time = time.time() - start_time
            return JSONResponse(
                {
                    'detail': f'La petición excedió el límite de {TIMEOUT_LIMIT} segundos.',
                    'processing_time': process_time
                },
                status_code=HTTP_504_GATEWAY_TIMEOUT
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
