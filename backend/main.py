"""
Adaptive Learning System — FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.database import init_db, close_db
from app.routers import auth, student, learning_path, assessment, tutor, analytics, engagement
print(">>> SERVER_START: Loading auth module from", getattr(auth, '__file__', 'UNKNOWN'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("Starting Adaptive Learning System...")
    await init_db()
    yield
    logger.info("Shutting down...")
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Driven Personalized Adaptive Learning System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(student.router, prefix="/student", tags=["Student"])
app.include_router(learning_path.router, prefix="/learning-path", tags=["Learning Path"])
app.include_router(assessment.router, prefix="/assessment", tags=["Assessment"])
app.include_router(tutor.router, prefix="/tutor", tags=["AI Tutor"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(engagement.router, prefix="/engagement", tags=["Engagement"])


@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "Adaptive Learning System API",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}
