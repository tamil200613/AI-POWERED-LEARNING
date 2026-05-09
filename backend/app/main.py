from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from app.database import init_db
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"DB init warning (continuing): {e}")
    yield
    try:
        from app.database import close_db
        await close_db()
    except Exception:
        pass

from app.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

from app.routers import auth, student, learning_path, assessment, tutor, analytics, engagement

app.include_router(auth.router,          prefix="/auth",          tags=["Authentication"])
app.include_router(student.router,       prefix="/student",       tags=["Student"])
app.include_router(learning_path.router, prefix="/learning-path", tags=["Learning Path"])
app.include_router(assessment.router,    prefix="/assessment",    tags=["Assessment"])
app.include_router(tutor.router,         prefix="/tutor",         tags=["AI Tutor"])
app.include_router(analytics.router,     prefix="/analytics",     tags=["Analytics"])
app.include_router(engagement.router,    prefix="/engagement",    tags=["Engagement"])

@app.get("/")
async def root():
    return {"message": "Adaptive Learning System API", "status": "running", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}