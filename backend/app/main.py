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
    settings = get_settings()
    
    print("=" * 60)
    print("🚀 Video to Audio API")
    print(f"📦 Version: 1.0.0")
    print(f"🗄️  Supabase: {'✅ Configurado' if settings.supabase_url else '❌ No configurado'}")
    print(f"⏱️  Max duración: {settings.max_duration_minutes} min")
    print(f"💾 Max tamaño archivo: {settings.max_file_size_mb} MB")
    print("=" * 60)
    
    yield
    
    # Shutdown
    cleaned = video.cleanup_old_files(max_age_hours=0)
    print("=" * 60)
    print(f"👋 Video to Audio API detenida")
    print(f"🧹 Archivos temporales limpiados: {cleaned}")
    print("=" * 60)


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
    
    # Middleware de timeout para peticiones largas (EXCEPTO uploads)
    @app.middleware("http")
    async def timeout_middleware(request: Request, call_next):
        start_time = time.time()
        
        # Excluir rutas de upload del timeout global
        EXCLUDED_PATHS = [
            "/api/upload",
            "/api/upload/download", 
            "/api/upload/extract",
            "/api/upload/streaming",  # Nueva ruta sin timeout
        ]
        
        # Log de request entrante (solo para endpoints importantes)
        if request.url.path.startswith("/api/") and not request.url.path == "/api/health":
            print(f"📥 {request.method} {request.url.path}")
        
        # Si la ruta está excluida, no aplicar timeout
        if any(request.url.path.startswith(path) for path in EXCLUDED_PATHS):
            return await call_next(request)
        
        # Para otras rutas, aplicar timeout de 10 minutos
        TIMEOUT_LIMIT = 600  # 10 minutos
        
        try:
            response = await asyncio.wait_for(call_next(request), timeout=TIMEOUT_LIMIT)
            
            # Log de respuesta exitosa (solo requests lentos)
            process_time = time.time() - start_time
            if process_time > 5:  # Solo loguear requests lentos
                print(f"⏱️  {request.method} {request.url.path} - {process_time:.2f}s")
            
            return response
        except asyncio.TimeoutError:
            process_time = time.time() - start_time
            print(f"❌ TIMEOUT: {request.method} {request.url.path} - {process_time:.2f}s")
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
