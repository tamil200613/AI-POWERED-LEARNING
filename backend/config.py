from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Adaptive Learning System"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://aluser:alpassword@localhost:5432/adaptive_learning"
    DATABASE_URL_SYNC: str = "postgresql://aluser:alpassword@localhost:5432/adaptive_learning"

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "adaptive_learning_content"

    # JWT
    SECRET_KEY: str = "change-this-secret-key-in-production-32chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # MLflow
    MLFLOW_TRACKING_URI: str = "./mlruns"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ML Model params
    STUDENT_EMBEDDING_DIM: int = 128
    IRT_DISCRIMINATION_PRIOR: float = 1.0
    RL_EPSILON_START: float = 1.0
    RL_EPSILON_END: float = 0.01
    RL_GAMMA: float = 0.99
    RL_LEARNING_RATE: float = 1e-3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
