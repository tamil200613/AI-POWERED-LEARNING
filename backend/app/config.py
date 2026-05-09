from pydantic_settings import BaseSettings
from typing import List
import json

class Settings(BaseSettings):
    APP_NAME: str = "Adaptive Learning System"
    DEBUG: bool = True
    DATABASE_URL: str = "postgresql+asyncpg://aluser:alpassword@localhost:5432/adaptive_learning"
    DATABASE_URL_SYNC: str = "postgresql://aluser:alpassword@localhost:5432/adaptive_learning"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    REDIS_URL: str = "redis://localhost:6379/0"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "adaptive_learning_content"
    SECRET_KEY: str = "super-secret-key-change-in-production-abc123xyz"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    MLFLOW_TRACKING_URI: str = "./mlruns"
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    STUDENT_EMBEDDING_DIM: int = 128
    RL_GAMMA: float = 0.99
    RL_LEARNING_RATE: float = 1e-3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()