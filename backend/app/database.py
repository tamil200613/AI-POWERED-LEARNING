from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import logging

logger = logging.getLogger(__name__)
from app.config import settings

connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}

engine = create_async_engine(settings.DATABASE_URL, echo=False, connect_args=connect_args)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

def get_qdrant():
    try:
        from qdrant_client import QdrantClient
        return QdrantClient(url=settings.QDRANT_URL, timeout=3)
    except Exception:
        return None

def ensure_qdrant_collection():
    try:
        from qdrant_client.models import Distance, VectorParams
        client = get_qdrant()
        if client is None:
            return
        for name, size in [("adaptive_learning_content", 128), ("content_embeddings", 768)]:
            try:
                client.get_collection(name)
            except Exception:
                client.create_collection(collection_name=name, vectors_config=VectorParams(size=size, distance=Distance.COSINE))
    except Exception as e:
        logger.warning(f"Qdrant skipped (no Docker needed): {e}")

async def init_db():
    async with engine.begin() as conn:
        from app.models import user, assessment
        await conn.run_sync(Base.metadata.create_all)
    logger.info("SQLite database tables created successfully")
    ensure_qdrant_collection()

async def close_db():
    await engine.dispose()