"""
scripts/init_db.py — Initialize PostgreSQL tables
Run: python scripts/init_db.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings
from app.database import Base
from app.models import user, assessment  # noqa: F401


async def init():
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("✅ PostgreSQL tables created successfully")


if __name__ == "__main__":
    asyncio.run(init())
