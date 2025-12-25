"""Document Processing Service API - OCR、レイアウト解析、チャンク分割"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info(f"Starting {settings.SERVICE_NAME} v{settings.VERSION}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"Docling device: {settings.DOCLING_DEVICE}")
    logger.info(f"OCR engine: {settings.OCR_DEFAULT_ENGINE}")
    logger.info(f"GPU OCR: {'enabled' if settings.OCR_GPU_ENABLED else 'disabled'}")
    yield
    logger.info(f"Shutting down {settings.SERVICE_NAME}")


# Create FastAPI application
app = FastAPI(
    title="Document Processing Service API",
    description="ドキュメント処理サービス - OCR、レイアウト解析、階層構造変換、チャンク分割",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
    }


@app.get("/", tags=["root"])
async def root():
    """Root endpoint."""
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs",
    }


# Import and register routers
from app.routers.process import router as process_router
from app.routers.ocr import router as ocr_router

# Register routers with API prefix
app.include_router(process_router, prefix="/api/doc", tags=["process"])
app.include_router(ocr_router, prefix="/api/doc/ocr", tags=["ocr"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8011,
        reload=settings.DEBUG,
    )
