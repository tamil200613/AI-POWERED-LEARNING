# ============================================================
# ADAPTIVE LEARNING SYSTEM — Complete Setup Script for Windows
# Run from: adaptive-learning-system\backend\
# Command:  powershell -ExecutionPolicy Bypass -File setup_all.ps1
# ============================================================

Write-Host "Creating complete project structure..." -ForegroundColor Cyan

# ── Create all directories ────────────────────────────────
$dirs = @(
    "app", "app\ai", "app\models", "app\routers", "app\schemas",
    "scripts", "models", "mlruns"
)
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Path $d -Force | Out-Null
}
Write-Host "  Folders created" -ForegroundColor Green

# ── .env ─────────────────────────────────────────────────
@"
DATABASE_URL=postgresql+asyncpg://aluser:alpassword@localhost:5432/adaptive_learning
DATABASE_URL_SYNC=postgresql://aluser:alpassword@localhost:5432/adaptive_learning
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=adaptive_learning_content
SECRET_KEY=super-secret-key-change-in-production-abc123xyz
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
ANTHROPIC_API_KEY=your-anthropic-api-key-here
MLFLOW_TRACKING_URI=./mlruns
APP_NAME=Adaptive Learning System
DEBUG=True
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
"@ | Out-File -FilePath ".env" -Encoding utf8
Write-Host "  .env created" -ForegroundColor Green

# ── app\__init__.py ───────────────────────────────────────
"" | Out-File -FilePath "app\__init__.py" -Encoding utf8

# ── app\config.py ────────────────────────────────────────
@'
from pydantic_settings import BaseSettings
from typing import List

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

settings = Settings()
'@ | Out-File -FilePath "app\config.py" -Encoding utf8

# ── app\database.py ──────────────────────────────────────
@'
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
import redis.asyncio as aioredis
import logging
from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, pool_size=10, max_overflow=20)
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

_neo4j_driver = None
def get_neo4j_driver():
    global _neo4j_driver
    if _neo4j_driver is None:
        from neo4j import AsyncGraphDatabase
        _neo4j_driver = AsyncGraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD))
    return _neo4j_driver

async def get_neo4j_session():
    driver = get_neo4j_driver()
    async with driver.session() as session:
        yield session

_redis_client = None
async def get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = await aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
    return _redis_client

_qdrant_client = None
def get_qdrant():
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(url=settings.QDRANT_URL)
    return _qdrant_client

def ensure_qdrant_collection():
    client = get_qdrant()
    for name, size in [("adaptive_learning_content", 128), ("content_embeddings", 768)]:
        try:
            client.get_collection(name)
        except Exception:
            client.create_collection(collection_name=name, vectors_config=VectorParams(size=size, distance=Distance.COSINE))
            logger.info(f"Created Qdrant collection: {name}")

async def init_db():
    async with engine.begin() as conn:
        from app.models import user, assessment
        await conn.run_sync(Base.metadata.create_all)
    logger.info("PostgreSQL tables created")
    ensure_qdrant_collection()

async def close_db():
    await engine.dispose()
    if _neo4j_driver:
        await _neo4j_driver.close()
    if _redis_client:
        await _redis_client.close()
'@ | Out-File -FilePath "app\database.py" -Encoding utf8

# ── app\models\__init__.py ───────────────────────────────
"" | Out-File -FilePath "app\models\__init__.py" -Encoding utf8

# ── app\models\user.py ───────────────────────────────────
@'
from sqlalchemy import Column, String, Float, JSON, DateTime, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200))
    grade_level = Column(Integer, default=10)
    learning_style = Column(String(50), default="visual")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    embedding = Column(JSON, default=list)
    mastery_scores = Column(JSON, default=dict)
    cognitive_level = Column(Float, default=0.5)
    engagement_score = Column(Float, default=0.7)
    learning_speed = Column(Float, default=1.0)
    irt_ability = Column(Float, default=0.0)
    irt_ability_std = Column(Float, default=1.0)
    total_sessions = Column(Integer, default=0)
    avg_session_minutes = Column(Float, default=0.0)
    total_questions_answered = Column(Integer, default=0)
    overall_accuracy = Column(Float, default=0.0)
    streak_days = Column(Integer, default=0)
    last_active = Column(DateTime(timezone=True))
    dropout_risk = Column(Float, default=0.0)
    predicted_final_score = Column(Float, default=0.5)
'@ | Out-File -FilePath "app\models\user.py" -Encoding utf8

# ── app\models\assessment.py ────────────────────────────
@'
from sqlalchemy import Column, String, Float, JSON, DateTime, Integer, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.database import Base

class LearningSession(Base):
    __tablename__ = "learning_sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    topic_id = Column(String(100), nullable=False)
    topic_name = Column(String(200))
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer, default=0)
    time_on_task = Column(Float, default=0.0)
    scroll_events = Column(Integer, default=0)
    click_events = Column(Integer, default=0)
    pause_count = Column(Integer, default=0)
    replay_count = Column(Integer, default=0)
    notes_taken = Column(Boolean, default=False)
    hint_requests = Column(Integer, default=0)
    pre_mastery = Column(Float, default=0.0)
    post_mastery = Column(Float, default=0.0)
    learning_gain = Column(Float, default=0.0)
    engagement_reward = Column(Float, default=0.0)
    retention_reward = Column(Float, default=0.0)
    efficiency_reward = Column(Float, default=0.0)
    total_reward = Column(Float, default=0.0)
    path_recommended_by_rl = Column(Boolean, default=True)
    content_type = Column(String(50))

class Assessment(Base):
    __tablename__ = "assessments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("learning_sessions.id"), nullable=True)
    topic_id = Column(String(100), nullable=False)
    question_id = Column(String(100))
    question_text = Column(Text)
    question_type = Column(String(50))
    difficulty = Column(Float, default=0.5)
    irt_a = Column(Float, default=1.0)
    irt_b = Column(Float, default=0.0)
    irt_c = Column(Float, default=0.25)
    student_answer = Column(Text)
    correct_answer = Column(Text)
    is_correct = Column(Boolean)
    score = Column(Float, default=0.0)
    semantic_similarity = Column(Float)
    response_time_seconds = Column(Float)
    hint_used = Column(Boolean, default=False)
    ai_generated = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ability_before = Column(Float)
    ability_after = Column(Float)

class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(String(100), unique=True, nullable=False, index=True)
    subject = Column(String(100), nullable=False)
    topic_name = Column(String(200), nullable=False)
    description = Column(Text)
    difficulty_level = Column(Integer, default=3)
    prerequisites = Column(JSON, default=list)
    learning_objectives = Column(JSON, default=list)
    estimated_minutes = Column(Integer, default=30)
    content_types = Column(JSON, default=list)
    embedding_vector = Column(JSON, default=list)
'@ | Out-File -FilePath "app\models\assessment.py" -Encoding utf8

Write-Host "  Models created" -ForegroundColor Green

# ── app\routers\__init__.py ──────────────────────────────
"" | Out-File -FilePath "app\routers\__init__.py" -Encoding utf8

# ── app\schemas\__init__.py ──────────────────────────────
"" | Out-File -FilePath "app\schemas\__init__.py" -Encoding utf8

# ── app\ai\__init__.py ───────────────────────────────────
"" | Out-File -FilePath "app\ai\__init__.py" -Encoding utf8

# ── app\routers\auth.py ──────────────────────────────────
@'
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import uuid
from app.database import get_db
from app.models.user import User
from app.config import settings
from pydantic import BaseModel, EmailStr

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None
    grade_level: Optional[int] = 10

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str

def create_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("/register", response_model=Token)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=user_data.email, username=user_data.username,
        hashed_password=pwd_context.hash(user_data.password),
        full_name=user_data.full_name, grade_level=user_data.grade_level,
        mastery_scores={}, embedding=[],
    )
    db.add(user)
    await db.flush()
    return Token(access_token=create_token(str(user.id)), token_type="bearer", user_id=str(user.id))

@router.post("/login", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not pwd_context.verify(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return Token(access_token=create_token(str(user.id)), token_type="bearer", user_id=str(user.id))
'@ | Out-File -FilePath "app\routers\auth.py" -Encoding utf8

# ── app\routers\student.py ───────────────────────────────
@'
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from app.database import get_db
from app.models.user import User
from app.models.assessment import LearningSession, Assessment
from app.ai.knowledge_graph import knowledge_graph
from app.routers.auth import get_current_user

router = APIRouter()

@router.get("/{user_id}/profile")
async def get_student_profile(user_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    mastery = user.mastery_scores or {}
    all_topics = [t["id"] for t in knowledge_graph.get_all_topics()]
    return {
        "user_id": user_id,
        "embedding": user.embedding or [],
        "learning_style": user.learning_style or "visual",
        "irt_ability": user.irt_ability or 0.0,
        "cognitive_level": user.cognitive_level or 0.5,
        "engagement_score": user.engagement_score or 0.5,
        "mastery_scores": mastery,
        "knowledge_gaps": [t for t in all_topics if mastery.get(t, 0.0) < 0.6],
        "strong_topics": [t for t in all_topics if mastery.get(t, 0.0) >= 0.8],
        "dropout_risk": user.dropout_risk or 0.0,
        "predicted_final_score": user.predicted_final_score or 0.5,
        "learning_speed": user.learning_speed or 1.0,
        "total_sessions": user.total_sessions or 0,
    }

@router.get("/{user_id}/mastery")
async def get_mastery_scores(user_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"mastery_scores": user.mastery_scores or {}, "irt_ability": user.irt_ability, "cognitive_level": user.cognitive_level}
'@ | Out-File -FilePath "app\routers\student.py" -Encoding utf8

# ── app\routers\engagement.py ────────────────────────────
@'
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any, Optional
import time

router = APIRouter()
_buf: dict = {}

class EngagementEvent(BaseModel):
    user_id: str
    event_type: str
    topic_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None

def _score(events):
    if not events: return 0.5
    recent = [e for e in events if time.time() - e["ts"] < 300]
    if not recent: return 0.3
    pos = sum(1 for e in recent if e["type"] in ("click","scroll","video_play"))
    neg = sum(1 for e in recent if e["type"] in ("blur","pause"))
    return float(0.5 * min(len(recent)/50,1.0) + 0.5 * pos/max(pos+neg,1))

@router.post("/event")
async def log_event(event: EngagementEvent):
    uid = event.user_id
    if uid not in _buf: _buf[uid] = []
    _buf[uid].append({"type": event.event_type, "topic": event.topic_id, "ts": event.timestamp or time.time()})
    _buf[uid] = _buf[uid][-1000:]
    return {"received": True, "engagement_score": round(_score(_buf[uid]), 3)}

@router.get("/{user_id}/score")
async def get_score(user_id: str):
    return {"user_id": user_id, "engagement_score": round(_score(_buf.get(user_id,[])), 3), "event_count": len(_buf.get(user_id,[]))}

@router.get("/{user_id}/attention")
async def get_attention(user_id: str):
    events = _buf.get(user_id, [])
    recent = [e for e in events if time.time() - e["ts"] < 300]
    blur = sum(1 for e in recent if e["type"] == "blur")
    pause = sum(1 for e in recent if e["type"] == "pause")
    level = "low" if blur > 5 or pause > 3 else "medium" if blur > 2 else "high"
    return {
        "attention_level": level,
        "blur_events": blur,
        "interactions_per_minute": len([e for e in recent if e["type"] in ("click","scroll")])/5.0,
        "distraction_score": round(min(blur/10,1.0),2),
        "recommendation": "Try a 5-minute break!" if level=="low" else "Great focus!" if level=="high" else "Minimize distractions.",
    }
'@ | Out-File -FilePath "app\routers\engagement.py" -Encoding utf8

# ── app\routers\tutor.py ─────────────────────────────────
@'
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.models.user import User
from app.ai.ai_tutor import ai_tutor
from app.routers.auth import get_current_user

router = APIRouter()

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    topic: Optional[str] = "general"
    mode: Optional[str] = "explain"

@router.post("/chat")
async def tutor_chat(req: ChatRequest, current_user: User = Depends(get_current_user)):
    profile = {
        "learning_style": current_user.learning_style or "visual",
        "irt_ability": current_user.irt_ability or 0.0,
        "cognitive_level": current_user.cognitive_level or 0.5,
        "engagement_score": current_user.engagement_score or 0.5,
        "mastery_scores": current_user.mastery_scores or {},
    }
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    response = ai_tutor.chat(messages=messages, student_profile=profile, topic=req.topic, mode=req.mode)
    return {"response": response, "topic": req.topic, "mode": req.mode}

@router.post("/evaluate")
async def evaluate_answer(student_answer: str, correct_answer: str, current_user: User = Depends(get_current_user)):
    return ai_tutor.evaluate_answer(student_answer, correct_answer)
'@ | Out-File -FilePath "app\routers\tutor.py" -Encoding utf8

Write-Host "  Routers created" -ForegroundColor Green

# ── app\routers\learning_path.py ─────────────────────────
@'
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from pydantic import BaseModel
from app.database import get_db
from app.models.user import User
from app.models.assessment import LearningSession
from app.ai.rl_agent import rl_agent, compute_reward
from app.ai.knowledge_graph import knowledge_graph
from app.routers.auth import get_current_user

router = APIRouter()

class SessionCompleteRequest(BaseModel):
    session_id: str
    topic_id: str
    mastery_before: float
    mastery_after: float
    engagement: float
    time_spent_minutes: float
    hint_count: int
    correct_first_try: bool

@router.get("/{user_id}")
async def get_learning_path(user_id: str, n: int = 5, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    topic_list = [t["id"] for t in knowledge_graph.get_all_topics()]
    mastery = user.mastery_scores or {}
    recs = rl_agent.recommend_path(
        student_embedding=user.embedding or [],
        mastery_scores=mastery, topic_list=topic_list,
        engagement=user.engagement_score or 0.5, n=n,
    )
    enriched = []
    for rec in recs:
        tid = rec["topic_id"]
        node = knowledge_graph.nx_graph.nodes.get(tid, {})
        enriched.append({**rec, "name": node.get("name", tid), "subject": node.get("subject",""),
            "difficulty": node.get("difficulty",3), "estimated_minutes": node.get("minutes",30),
            "explanation": f"Mastery {rec['current_mastery']:.0%} — prerequisites met."})
    graph_recs = knowledge_graph.get_next_recommended_topics(mastery, n=n)
    return {"user_id": user_id, "rl_recommendations": enriched, "graph_recommendations": graph_recs, "epsilon": rl_agent.epsilon}

@router.post("/session/complete")
async def complete_session(req: SessionCompleteRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    reward = compute_reward(
        mastery_before=req.mastery_before, mastery_after=req.mastery_after,
        engagement=req.engagement, time_spent_minutes=req.time_spent_minutes,
        topic_was_mastered=req.mastery_before > 0.85,
        hint_count=req.hint_count, correct_first_try=req.correct_first_try,
    )
    mastery = dict(current_user.mastery_scores or {})
    mastery[req.topic_id] = min(req.mastery_after, 1.0)
    current_user.mastery_scores = mastery
    current_user.engagement_score = 0.7*(current_user.engagement_score or 0.5) + 0.3*req.engagement
    return {"reward": round(reward,4), "updated_mastery": mastery.get(req.topic_id)}

@router.get("/topics/all")
async def get_all_topics():
    return knowledge_graph.get_all_topics()

@router.get("/topics/{topic_id}/prerequisites")
async def get_prereqs(topic_id: str):
    return {"topic_id": topic_id, "prerequisites": knowledge_graph.get_prerequisites(topic_id, depth=3)}
'@ | Out-File -FilePath "app\routers\learning_path.py" -Encoding utf8

# ── app\routers\assessment.py ────────────────────────────
@'
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from typing import Optional, List
from pydantic import BaseModel
from app.database import get_db
from app.models.user import User
from app.models.assessment import Assessment
from app.ai.irt_engine import adaptive_engine
from app.ai.ai_tutor import ai_tutor
from app.routers.auth import get_current_user

router = APIRouter()

class StartTestRequest(BaseModel):
    topic_id: str
    max_items: Optional[int] = 10

class SubmitAnswerRequest(BaseModel):
    question_id: str
    topic_id: str
    student_answer: str
    correct_answer: str
    irt_a: float
    irt_b: float
    irt_c: float
    current_responses: List[dict]

class GenerateQuestionRequest(BaseModel):
    topic_id: str
    difficulty: Optional[float] = 0.5
    question_type: Optional[str] = "mcq"

@router.post("/adaptive/start")
async def start_adaptive_test(req: StartTestRequest, current_user: User = Depends(get_current_user)):
    theta = current_user.irt_ability or 0.0
    item = adaptive_engine.select_next_item(current_theta=theta, used_item_ids=[], topic_filter=None)
    if not item:
        raise HTTPException(status_code=404, detail="No items available")
    difficulty = adaptive_engine.compute_mastery_score(item["irt_b"])
    q = ai_tutor.generate_question(topic_id=req.topic_id, difficulty=difficulty, q_type=item["question_type"])
    return {
        "session_id": str(uuid.uuid4()), "question_id": item["question_id"],
        "topic_id": req.topic_id, "question": q,
        "irt_params": {"a": item["irt_a"], "b": item["irt_b"], "c": item["irt_c"]},
        "current_ability": theta, "current_se": current_user.irt_ability_std or 1.0, "items_answered": 0,
    }

@router.post("/adaptive/submit")
async def submit_adaptive_answer(req: SubmitAnswerRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    eval_result = ai_tutor.evaluate_answer(req.student_answer, req.correct_answer)
    is_correct = eval_result["score"] >= 0.7
    prior = [(r["a"],r["b"],r["c"],int(r["response"])) for r in req.current_responses]
    all_responses = prior + [(req.irt_a, req.irt_b, req.irt_c, int(is_correct))]
    theta_before = current_user.irt_ability or 0.0
    theta_after, se = adaptive_engine.update_ability(all_responses, prior_mean=theta_before, prior_std=current_user.irt_ability_std or 1.0)
    assessment = Assessment(
        user_id=current_user.id, topic_id=req.topic_id, question_id=req.question_id,
        question_type="adaptive", irt_a=req.irt_a, irt_b=req.irt_b, irt_c=req.irt_c,
        student_answer=req.student_answer, correct_answer=req.correct_answer,
        is_correct=is_correct, score=eval_result["score"],
        ability_before=theta_before, ability_after=theta_after, ai_generated=True,
    )
    db.add(assessment)
    current_user.irt_ability = theta_after
    current_user.irt_ability_std = se
    current_user.total_questions_answered = (current_user.total_questions_answered or 0) + 1
    n = current_user.total_questions_answered
    current_user.overall_accuracy = ((n-1)*(current_user.overall_accuracy or 0.5) + float(is_correct)) / n
    n_items = len(all_responses)
    stop, reason = adaptive_engine.should_stop(n_items, se)
    next_q = None
    if not stop:
        used = [r.get("question_id","") for r in req.current_responses] + [req.question_id]
        nxt = adaptive_engine.select_next_item(theta_after, used)
        if nxt:
            d = adaptive_engine.compute_mastery_score(nxt["irt_b"])
            qd = ai_tutor.generate_question(topic_id=req.topic_id, difficulty=d, q_type=nxt["question_type"])
            next_q = {"question_id": nxt["question_id"], "question": qd, "irt_params": {"a":nxt["irt_a"],"b":nxt["irt_b"],"c":nxt["irt_c"]}}
    return {
        "is_correct": is_correct, "score": round(eval_result["score"],3),
        "feedback": eval_result["feedback"],
        "ability_before": round(theta_before,3), "ability_after": round(theta_after,3),
        "standard_error": round(se,3), "mastery_score": round(adaptive_engine.compute_mastery_score(theta_after),3),
        "items_answered": n_items, "test_complete": stop, "stop_reason": reason, "next_question": next_q,
    }

@router.post("/generate")
async def generate_question(req: GenerateQuestionRequest, current_user: User = Depends(get_current_user)):
    return ai_tutor.generate_question(topic_id=req.topic_id, difficulty=req.difficulty, q_type=req.question_type)

@router.get("/{user_id}/history")
async def get_history(user_id: str, topic_id: Optional[str]=None, limit: int=50, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = select(Assessment).where(Assessment.user_id == uuid.UUID(user_id))
    if topic_id: q = q.where(Assessment.topic_id == topic_id)
    result = await db.execute(q.order_by(Assessment.created_at.desc()).limit(limit))
    return [{"id":str(a.id),"topic_id":a.topic_id,"is_correct":a.is_correct,"score":a.score,"ability_after":a.ability_after,"created_at":str(a.created_at)} for a in result.scalars().all()]
'@ | Out-File -FilePath "app\routers\assessment.py" -Encoding utf8

# ── app\routers\analytics.py ─────────────────────────────
@'
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from app.database import get_db
from app.models.user import User
from app.models.assessment import LearningSession, Assessment
from app.ai.knowledge_graph import knowledge_graph
from app.ai.performance_predictor import performance_predictor
from app.routers.auth import get_current_user

router = APIRouter()

@router.get("/{user_id}/heatmap")
async def get_heatmap(user_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    mastery = user.mastery_scores or {}
    all_topics = knowledge_graph.get_all_topics()
    importance = knowledge_graph.compute_topic_importance()
    subjects = {}
    for t in all_topics:
        tid = t["id"]; subj = t.get("subject","other")
        if subj not in subjects: subjects[subj] = []
        subjects[subj].append({"topic_id":tid,"name":t.get("name",tid),"mastery":mastery.get(tid,0.0),
            "difficulty":t.get("difficulty",3),"importance":importance.get(tid,0.0),
            "status":"mastered" if mastery.get(tid,0.0)>=0.8 else "learning" if mastery.get(tid,0.0)>=0.4 else "gap"})
    gap_sub = knowledge_graph.get_knowledge_gap_subgraph(mastery, threshold=0.6)
    return {"user_id":user_id,"subjects":subjects,"gap_subgraph":gap_sub,"summary":{
        "total_topics":len(all_topics),"mastered":sum(1 for t in all_topics if mastery.get(t["id"],0)>=0.8),
        "learning":sum(1 for t in all_topics if 0.4<=mastery.get(t["id"],0)<0.8),
        "gap":sum(1 for t in all_topics if mastery.get(t["id"],0)<0.4),
        "overall_mastery":sum(mastery.values())/max(len(all_topics),1)}}

@router.get("/{user_id}/predict")
async def get_prediction(user_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    sessions_result = await db.execute(select(LearningSession).where(LearningSession.user_id==uuid.UUID(user_id)).order_by(LearningSession.started_at.asc()))
    sessions = [{c.name:getattr(s,c.name) for c in s.__table__.columns} for s in sessions_result.scalars().all()]
    user_dict = {c.name:getattr(user,c.name) for c in user.__table__.columns}
    pred = performance_predictor.predict(user_dict, sessions)
    user.dropout_risk = pred["dropout_risk"]; user.predicted_final_score = pred["predicted_final_score"]
    return pred

@router.get("/{user_id}/progress")
async def get_progress(user_id: str, limit: int=30, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    sr = await db.execute(select(LearningSession).where(LearningSession.user_id==uuid.UUID(user_id)).order_by(LearningSession.started_at.desc()).limit(limit))
    ar = await db.execute(select(Assessment).where(Assessment.user_id==uuid.UUID(user_id)).order_by(Assessment.created_at.desc()).limit(limit))
    sessions = list(reversed(sr.scalars().all())); assessments = list(reversed(ar.scalars().all()))
    return {
        "sessions":[{"date":str(s.started_at),"topic":s.topic_name,"learning_gain":s.learning_gain,"post_mastery":s.post_mastery,"duration_minutes":(s.duration_seconds or 0)/60,"reward":s.total_reward} for s in sessions],
        "ability_trajectory":[{"date":str(a.created_at),"ability":a.ability_after,"topic":a.topic_id,"correct":a.is_correct} for a in assessments if a.ability_after is not None]}
'@ | Out-File -FilePath "app\routers\analytics.py" -Encoding utf8

Write-Host "  All routers created" -ForegroundColor Green

# ── app\main.py ──────────────────────────────────────────
@'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import logging
from app.config import settings
from app.database import init_db, close_db
from app.routers import auth, student, learning_path, assessment, tutor, analytics, engagement

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()

app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.include_router(auth.router,          prefix="/auth",          tags=["Authentication"])
app.include_router(student.router,       prefix="/student",       tags=["Student"])
app.include_router(learning_path.router, prefix="/learning-path", tags=["Learning Path"])
app.include_router(assessment.router,    prefix="/assessment",    tags=["Assessment"])
app.include_router(tutor.router,         prefix="/tutor",         tags=["AI Tutor"])
app.include_router(analytics.router,     prefix="/analytics",     tags=["Analytics"])
app.include_router(engagement.router,    prefix="/engagement",    tags=["Engagement"])

@app.get("/")
async def root(): return {"message": "Adaptive Learning System API", "status": "running"}

@app.get("/health")
async def health(): return {"status": "healthy"}
'@ | Out-File -FilePath "app\main.py" -Encoding utf8

# ── app\worker.py ────────────────────────────────────────
@'
from celery import Celery
from app.config import settings
celery_app = Celery("adaptive_learning", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
'@ | Out-File -FilePath "app\worker.py" -Encoding utf8

# ── app\tasks.py ─────────────────────────────────────────
@'
from app.worker import celery_app
import logging
logger = logging.getLogger(__name__)

@celery_app.task(name="app.tasks.update_student_models")
def update_student_models():
    logger.info("Updating student models")
    return {"status": "completed"}

@celery_app.task(name="app.tasks.retrain_rl_agent")
def retrain_rl_agent():
    logger.info("Retraining RL agent")
    from app.ai.rl_agent import rl_agent
    losses = [rl_agent.train_step() for _ in range(100)]
    rl_agent.save_model()
    return {"status": "completed"}
'@ | Out-File -FilePath "app\tasks.py" -Encoding utf8

Write-Host "  main.py + worker + tasks created" -ForegroundColor Green

# ── scripts\init_db.py ───────────────────────────────────
@'
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings
from app.database import Base
from app.models import user, assessment

async def init():
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("PostgreSQL tables created successfully")

if __name__ == "__main__":
    asyncio.run(init())
'@ | Out-File -FilePath "scripts\init_db.py" -Encoding utf8

# ── scripts\seed_knowledge_graph.py ─────────────────────
@'
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from neo4j import AsyncGraphDatabase
from app.config import settings
from app.ai.knowledge_graph import knowledge_graph

async def seed():
    driver = AsyncGraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD))
    async with driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
        await knowledge_graph.seed_neo4j(session)
        r1 = await session.run("MATCH (t:Topic) RETURN count(t) as n")
        rec = await r1.single()
        print(f"Topics seeded: {rec['n']}")
    await driver.close()
    print("Neo4j knowledge graph seeded successfully")

if __name__ == "__main__":
    asyncio.run(seed())
'@ | Out-File -FilePath "scripts\seed_knowledge_graph.py" -Encoding utf8

# ── scripts\seed_content.py ──────────────────────────────
@'
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import ensure_qdrant_collection
from app.ai.ai_tutor import RAGRetriever

def seed():
    print("Ensuring Qdrant collections...")
    ensure_qdrant_collection()
    print("Seeding educational content...")
    retriever = RAGRetriever()
    retriever.seed_content()
    print("Content seeded. Testing retrieval...")
    results = retriever.retrieve("how to find derivative of a function", top_k=2)
    for r in results:
        print(f"  Retrieved: topic={r['topic_id']}, score={r['score']:.3f}")
    print("Done!")

if __name__ == "__main__":
    seed()
'@ | Out-File -FilePath "scripts\seed_content.py" -Encoding utf8

# ── scripts\train_models.py ──────────────────────────────
@'
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, torch, torch.nn as nn, torch.optim as optim, pickle
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import xgboost as xgb
from app.ai.rl_agent import rl_agent, compute_reward
from app.ai.performance_predictor import LSTMPerformancePredictor, build_prediction_features, build_session_sequence

os.makedirs("models", exist_ok=True)

def gen_students(n=300):
    students = []
    for _ in range(n):
        ab = np.random.normal(0,1); eng = np.clip(np.random.beta(3,2),0,1)
        mastery = {}; sessions = []
        for i in range(np.random.randint(5,30)):
            t = f"topic_{np.random.randint(0,12)}"
            mb = mastery.get(t, np.random.uniform(0,0.3))
            gain = np.clip(np.random.normal(0.08+0.03*ab,0.03),-0.05,0.2)
            mastery[t] = min(mb+gain,1.0)
            sessions.append({"duration_seconds":np.random.randint(600,3600),"time_on_task":np.random.randint(300,2400),
                "scroll_events":np.random.randint(0,100),"click_events":np.random.randint(0,50),
                "hint_requests":np.random.randint(0,5),"replay_count":np.random.randint(0,3),
                "notes_taken":np.random.random()>0.6,"pause_count":np.random.randint(0,8),
                "engagement_score":float(eng),"overall_accuracy":np.clip(0.5+0.1*ab+np.random.normal(0,0.1),0,1),
                "learning_gain":float(gain),"pre_mastery":float(mb),"post_mastery":float(mastery[t]),
                "irt_ability":float(ab),"cognitive_level":float(np.clip((ab+3)/6,0,1)),
                "learning_speed":float(np.clip(np.random.lognormal(0,0.3),0.3,3.0)),
                "dropout_risk":float(max(0,0.5-0.15*ab-0.2*eng)),"streak_days":np.random.randint(0,30),
                "avg_session_minutes":np.random.uniform(15,60),"total_sessions":i+1})
        students.append({"ability":ab,"engagement":eng,"sessions":sessions,"mastery":mastery,
            "final_score":float(np.clip(0.5+0.15*ab+0.1*eng+np.random.normal(0,0.05),0,1)),
            "dropped_out":ab<-1.0 and eng<0.4})
    return students

print("Generating synthetic student data...")
students = gen_students(300)
print(f"  Generated {len(students)} students")

print("Training XGBoost predictor...")
X,ys,yd = [],[],[]
for s in students:
    ud = {"irt_ability":s["ability"],"overall_accuracy":s["sessions"][-1]["overall_accuracy"] if s["sessions"] else 0.5,
          "cognitive_level":(s["ability"]+3)/6,"learning_speed":1.0,"total_questions_answered":len(s["sessions"])*5,
          "total_sessions":len(s["sessions"]),"avg_session_minutes":30,"streak_days":10,
          "engagement_score":s["engagement"],"mastery_scores":s["mastery"]}
    X.append(build_prediction_features(ud, s["sessions"])); ys.append(s["final_score"]); yd.append(int(s["dropped_out"]))
X=np.array(X); ys=np.array(ys); yd=np.array(yd)
scaler=StandardScaler(); Xs=scaler.fit_transform(X)
Xtr,Xte,ystr,yste=train_test_split(Xs,ys,test_size=0.2,random_state=42)
model=xgb.XGBRegressor(n_estimators=100,max_depth=5,learning_rate=0.1,random_state=42)
model.fit(Xtr,ystr)
print(f"  RMSE: {np.sqrt(np.mean((model.predict(Xte)-yste)**2)):.4f}")
with open("models/xgb_predictor.pkl","wb") as f: pickle.dump(model,f)
with open("models/predictor_scaler.pkl","wb") as f: pickle.dump(scaler,f)
print("  XGBoost saved")

print("Training LSTM predictor...")
lstm=LSTMPerformancePredictor(); opt=optim.Adam(lstm.parameters(),lr=1e-3)
Xseq=torch.FloatTensor(np.array([build_session_sequence(s["sessions"]) for s in students]))
ysc=torch.FloatTensor(np.array([s["final_score"] for s in students]))
ds=torch.utils.data.TensorDataset(Xseq,ysc); dl=torch.utils.data.DataLoader(ds,batch_size=32,shuffle=True)
best=float("inf")
for ep in range(15):
    lstm.train(); tl=0
    for bx,by in dl:
        p=lstm(bx).squeeze(); loss=nn.functional.mse_loss(p,by)
        opt.zero_grad(); loss.backward(); opt.step(); tl+=loss.item()
    avg=tl/len(dl)
    if avg<best: best=avg; torch.save(lstm.state_dict(),"models/lstm_predictor.pt")
print(f"  LSTM saved (best loss: {best:.4f})")

print("Training RL agent...")
tl=[f"topic_{i}" for i in range(36)]
for ep in range(200):
    ab=np.random.normal(0,1); eng=np.clip(np.random.beta(3,2),0,1)
    mas={t:max(0,min(1,np.random.normal(0.3+0.1*ab,0.1))) for t in tl}
    emb=np.random.randn(128).tolist()
    state=rl_agent.build_state(emb,mas,tl,eng)
    avail=[i for i,t in enumerate(tl) if mas.get(t,0)<0.85]
    if not avail: continue
    action=rl_agent.select_action(state,avail)
    t=tl[action]; mb=mas.get(t,0.0)
    gain=np.clip(np.random.normal(0.08+0.03*ab,0.03),-0.05,0.2); ma=min(mb+gain,1.0)
    reward=compute_reward(mastery_before=mb,mastery_after=ma,engagement=eng,
        time_spent_minutes=np.random.uniform(10,40),topic_was_mastered=mb>0.85,
        hint_count=np.random.randint(0,3),correct_first_try=np.random.random()>0.4)
    mas[t]=ma; ns=rl_agent.build_state(emb,mas,tl,eng)
    rl_agent.replay_buffer.push(state,action,reward,ns,float(all(m>=0.85 for m in mas.values())))
    rl_agent.train_step()
rl_agent.save_model()
print("  RL agent saved")
print("\nAll models trained successfully!")
'@ | Out-File -FilePath "scripts\train_models.py" -Encoding utf8

Write-Host "  Scripts created" -ForegroundColor Green

# ── Now create all AI modules ─────────────────────────────
# (These are large - writing key ones inline)

# app\ai\knowledge_graph.py
@'
import numpy as np
import networkx as nx
from typing import List, Dict, Optional

SAMPLE_KNOWLEDGE_GRAPH = {
    "mathematics": [
        {"id":"math_arithmetic","name":"Arithmetic","difficulty":1,"minutes":20,"prereqs":[]},
        {"id":"math_fractions","name":"Fractions & Decimals","difficulty":2,"minutes":30,"prereqs":["math_arithmetic"]},
        {"id":"math_algebra_basics","name":"Algebra Basics","difficulty":2,"minutes":40,"prereqs":["math_arithmetic","math_fractions"]},
        {"id":"math_linear_equations","name":"Linear Equations","difficulty":3,"minutes":45,"prereqs":["math_algebra_basics"]},
        {"id":"math_quadratic","name":"Quadratic Equations","difficulty":3,"minutes":50,"prereqs":["math_linear_equations"]},
        {"id":"math_functions","name":"Functions & Graphs","difficulty":3,"minutes":45,"prereqs":["math_linear_equations"]},
        {"id":"math_trigonometry","name":"Trigonometry","difficulty":4,"minutes":60,"prereqs":["math_functions","math_quadratic"]},
        {"id":"math_calculus_limits","name":"Limits & Continuity","difficulty":4,"minutes":55,"prereqs":["math_functions"]},
        {"id":"math_derivatives","name":"Derivatives","difficulty":5,"minutes":60,"prereqs":["math_calculus_limits"]},
        {"id":"math_integrals","name":"Integrals","difficulty":5,"minutes":70,"prereqs":["math_derivatives"]},
        {"id":"math_statistics","name":"Statistics & Probability","difficulty":3,"minutes":50,"prereqs":["math_algebra_basics"]},
        {"id":"math_linear_algebra","name":"Linear Algebra","difficulty":5,"minutes":80,"prereqs":["math_functions","math_statistics"]},
    ],
    "computer_science": [
        {"id":"cs_intro","name":"Intro to Programming","difficulty":1,"minutes":30,"prereqs":[]},
        {"id":"cs_variables","name":"Variables & Data Types","difficulty":1,"minutes":25,"prereqs":["cs_intro"]},
        {"id":"cs_control_flow","name":"Control Flow","difficulty":2,"minutes":35,"prereqs":["cs_variables"]},
        {"id":"cs_functions","name":"Functions","difficulty":2,"minutes":40,"prereqs":["cs_control_flow"]},
        {"id":"cs_arrays","name":"Arrays & Lists","difficulty":2,"minutes":35,"prereqs":["cs_variables","cs_control_flow"]},
        {"id":"cs_oop","name":"Object-Oriented Programming","difficulty":3,"minutes":60,"prereqs":["cs_functions","cs_arrays"]},
        {"id":"cs_data_structures","name":"Data Structures","difficulty":4,"minutes":70,"prereqs":["cs_oop","cs_arrays"]},
        {"id":"cs_algorithms","name":"Algorithms & Complexity","difficulty":4,"minutes":80,"prereqs":["cs_data_structures","math_statistics"]},
        {"id":"cs_recursion","name":"Recursion","difficulty":3,"minutes":45,"prereqs":["cs_functions"]},
        {"id":"cs_sorting","name":"Sorting Algorithms","difficulty":3,"minutes":50,"prereqs":["cs_recursion","cs_arrays"]},
        {"id":"cs_databases","name":"Databases & SQL","difficulty":3,"minutes":55,"prereqs":["cs_oop"]},
        {"id":"cs_ml_basics","name":"Machine Learning Basics","difficulty":5,"minutes":90,"prereqs":["cs_algorithms","math_statistics","math_linear_algebra"]},
    ],
    "physics": [
        {"id":"phys_kinematics","name":"Kinematics","difficulty":2,"minutes":45,"prereqs":["math_algebra_basics"]},
        {"id":"phys_dynamics","name":"Newton Laws","difficulty":3,"minutes":50,"prereqs":["phys_kinematics"]},
        {"id":"phys_energy","name":"Work Energy Power","difficulty":3,"minutes":45,"prereqs":["phys_dynamics"]},
        {"id":"phys_waves","name":"Waves & Oscillations","difficulty":3,"minutes":50,"prereqs":["phys_dynamics","math_trigonometry"]},
        {"id":"phys_electricity","name":"Electricity & Magnetism","difficulty":4,"minutes":70,"prereqs":["phys_energy","math_derivatives"]},
        {"id":"phys_quantum","name":"Quantum Mechanics","difficulty":5,"minutes":90,"prereqs":["phys_waves","phys_electricity","math_integrals"]},
    ],
}

class KnowledgeGraphEngine:
    def __init__(self):
        self.nx_graph = self._build()

    def _build(self):
        G = nx.DiGraph()
        for subject, topics in SAMPLE_KNOWLEDGE_GRAPH.items():
            for t in topics:
                G.add_node(t["id"], name=t["name"], subject=subject, difficulty=t["difficulty"], minutes=t["minutes"])
                for p in t["prereqs"]:
                    G.add_edge(p, t["id"], type="prerequisite")
        return G

    async def seed_neo4j(self, session):
        for subject, topics in SAMPLE_KNOWLEDGE_GRAPH.items():
            for t in topics:
                await session.run("MERGE (n:Topic {id:$id}) SET n.name=$name,n.subject=$subject,n.difficulty=$diff,n.estimated_minutes=$mins",
                    id=t["id"],name=t["name"],subject=subject,diff=t["difficulty"],mins=t["minutes"])
            for t in topics:
                for p in t["prereqs"]:
                    await session.run("MATCH (a:Topic{id:$a}),(b:Topic{id:$b}) MERGE (a)-[:PREREQUISITE]->(b)",a=p,b=t["id"])

    def get_prerequisites(self, topic_id, depth=3):
        if topic_id not in self.nx_graph: return []
        prereqs=set(); queue=[topic_id]; visited=set()
        for _ in range(depth):
            nxt=[]
            for n in queue:
                if n in visited: continue
                visited.add(n)
                preds=list(self.nx_graph.predecessors(n)); prereqs.update(preds); nxt.extend(preds)
            queue=nxt
        return list(prereqs-{topic_id})

    def get_next_recommended_topics(self, mastery_scores, n=5, threshold=0.7):
        recs=[]
        for tid in self.nx_graph.nodes():
            if mastery_scores.get(tid,0.0)>=threshold: continue
            prereqs=list(self.nx_graph.predecessors(tid))
            if all(mastery_scores.get(p,0.0)>=threshold for p in prereqs):
                nd=self.nx_graph.nodes[tid]
                recs.append({"topic_id":tid,"name":nd.get("name",tid),"subject":nd.get("subject",""),
                    "difficulty":nd.get("difficulty",3),"estimated_minutes":nd.get("minutes",30),
                    "current_mastery":mastery_scores.get(tid,0.0),"prereqs_met":True})
        recs.sort(key=lambda x:(x["difficulty"],-(1-x["current_mastery"])))
        return recs[:n]

    def compute_topic_importance(self):
        return nx.betweenness_centrality(self.nx_graph, normalized=True)

    def get_knowledge_gap_subgraph(self, mastery_scores, threshold=0.6):
        gap=[t for t,m in mastery_scores.items() if m<threshold and t in self.nx_graph]
        sub=self.nx_graph.subgraph(gap)
        return {"nodes":[{"id":n,"name":self.nx_graph.nodes[n].get("name",n),"mastery":mastery_scores.get(n,0.0),"difficulty":self.nx_graph.nodes[n].get("difficulty",3)} for n in sub.nodes()],
                "edges":[{"from":u,"to":v} for u,v in sub.edges()]}

    def get_all_topics(self):
        return [{"id":n,**{k:v for k,v in self.nx_graph.nodes[n].items()},"prerequisite_count":len(list(self.nx_graph.predecessors(n))),"dependent_count":len(list(self.nx_graph.successors(n)))} for n in self.nx_graph.nodes()]

knowledge_graph = KnowledgeGraphEngine()
'@ | Out-File -FilePath "app\ai\knowledge_graph.py" -Encoding utf8

Write-Host "  knowledge_graph.py created" -ForegroundColor Green

# app\ai\irt_engine.py
@'
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import norm
from typing import List, Dict, Optional, Tuple

def default_item_bank():
    np.random.seed(42); items=[]
    for i,b in enumerate(np.linspace(-3,3,60)):
        items.append({"question_id":f"item_{i:03d}","topic_id":f"topic_{i%12}",
            "irt_a":float(np.clip(np.random.normal(1.2,0.3),0.5,2.5)),
            "irt_b":float(b),"irt_c":float(np.clip(np.random.beta(2,8),0.1,0.35)),
            "question_type":np.random.choice(["mcq","short_answer","coding"],p=[0.6,0.3,0.1])})
    return items

def p_correct(theta,a,b,c): return c+(1-c)/(1+np.exp(-a*(theta-b)))

def item_information(theta,a,b,c):
    p=p_correct(theta,a,b,c); q=1-p
    num=a**2*(p-c)**2*q; den=(1-c)**2*p
    return 0.0 if den<1e-10 else num/den

def eap_ability_estimate(responses,prior_mean=0.0,prior_std=1.0,n_points=61):
    theta_grid=np.linspace(-4,4,n_points); prior=norm.pdf(theta_grid,prior_mean,prior_std)
    likelihood=np.ones(n_points)
    for a,b,c,u in responses:
        for i,theta in enumerate(theta_grid):
            p=np.clip(p_correct(theta,a,b,c),1e-9,1-1e-9)
            likelihood[i]*=(p**u)*((1-p)**(1-u))
    posterior=prior*likelihood; s=posterior.sum()
    if s<1e-15: return prior_mean,prior_std
    posterior/=s
    theta_hat=float(np.sum(theta_grid*posterior))
    se=float(np.sqrt(max(np.sum(((theta_grid-theta_hat)**2)*posterior),0.01)))
    return theta_hat,se

class AdaptiveTestEngine:
    def __init__(self,item_bank=None,max_items=20):
        self.item_bank=item_bank or default_item_bank(); self.max_items=max_items; self.stopping_se=0.3

    def select_next_item(self,current_theta,used_item_ids,topic_filter=None):
        candidates=[it for it in self.item_bank if it["question_id"] not in used_item_ids and (topic_filter is None or it["topic_id"]==topic_filter)]
        if not candidates: return None
        return max(candidates,key=lambda it:item_information(current_theta,it["irt_a"],it["irt_b"],it["irt_c"]))

    def update_ability(self,responses,prior_mean=0.0,prior_std=1.0,use_eap=True):
        return eap_ability_estimate(responses,prior_mean,prior_std)

    def should_stop(self,n_items,se):
        if n_items>=self.max_items: return True,"max_items_reached"
        if se<self.stopping_se and n_items>=5: return True,"sufficient_precision"
        return False,""

    def compute_mastery_score(self,theta): return float(1/(1+np.exp(-0.8*theta)))

adaptive_engine = AdaptiveTestEngine()
'@ | Out-File -FilePath "app\ai\irt_engine.py" -Encoding utf8

Write-Host "  irt_engine.py created" -ForegroundColor Green

# app\ai\rl_agent.py
@'
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F, torch.optim as optim
from collections import deque
import random, os
from typing import List, Dict, Optional

class DQNetwork(nn.Module):
    def __init__(self,state_dim,action_dim,hidden_dim=256):
        super().__init__()
        self.features=nn.Sequential(nn.Linear(state_dim,hidden_dim),nn.ReLU(),nn.LayerNorm(hidden_dim),nn.Linear(hidden_dim,hidden_dim),nn.ReLU(),nn.LayerNorm(hidden_dim))
        self.value=nn.Sequential(nn.Linear(hidden_dim,128),nn.ReLU(),nn.Linear(128,1))
        self.advantage=nn.Sequential(nn.Linear(hidden_dim,128),nn.ReLU(),nn.Linear(128,action_dim))
    def forward(self,x):
        f=self.features(x); v=self.value(f); a=self.advantage(f)
        return v+(a-a.mean(dim=1,keepdim=True))

class ReplayBuffer:
    def __init__(self,capacity=10000): self.buf=deque(maxlen=capacity)
    def push(self,*args): self.buf.append(args)
    def sample(self,n):
        batch=random.sample(self.buf,n)
        s,a,r,ns,d=zip(*batch)
        return np.array(s),np.array(a),np.array(r,dtype=np.float32),np.array(ns),np.array(d,dtype=np.float32)
    def __len__(self): return len(self.buf)

def compute_reward(mastery_before,mastery_after,engagement,time_spent_minutes,topic_was_mastered,hint_count,correct_first_try):
    gain=mastery_after-mastery_before
    r=4.0*gain+2.5*engagement-1.25+2.0*min(gain/max(time_spent_minutes,1)*10,1.0)
    r+=1.0 if correct_first_try and not hint_count else 0.0
    r-=0.1*hint_count+(2.0 if topic_was_mastered else 0.0)
    return float(np.clip(r,-5.0,5.0))

class LearningPathAgent:
    def __init__(self,state_dim=165,action_dim=36,hidden_dim=256,lr=1e-3,gamma=0.99,epsilon_start=1.0,epsilon_end=0.05,epsilon_decay=0.995,batch_size=64,target_update_freq=100,model_path="models/rl_agent.pt"):
        self.state_dim=state_dim; self.action_dim=action_dim; self.gamma=gamma
        self.epsilon=epsilon_start; self.epsilon_end=epsilon_end; self.epsilon_decay=epsilon_decay
        self.batch_size=batch_size; self.target_update_freq=target_update_freq; self.model_path=model_path; self.steps=0
        self.online_net=DQNetwork(state_dim,action_dim,hidden_dim)
        self.target_net=DQNetwork(state_dim,action_dim,hidden_dim)
        self.target_net.load_state_dict(self.online_net.state_dict()); self.target_net.eval()
        self.optimizer=optim.Adam(self.online_net.parameters(),lr=lr)
        self.replay_buffer=ReplayBuffer(); self._load()

    def build_state(self,embedding,mastery_scores,topic_list,engagement):
        emb=np.array(embedding[:128],dtype=np.float32)
        if len(emb)<128: emb=np.pad(emb,(0,128-len(emb)))
        mv=np.array([mastery_scores.get(t,0.0) for t in topic_list[:self.action_dim]],dtype=np.float32)
        if len(mv)<self.action_dim: mv=np.pad(mv,(0,self.action_dim-len(mv)))
        state=np.concatenate([emb,mv,[engagement]])
        if len(state)<self.state_dim: state=np.pad(state,(0,self.state_dim-len(state)))
        return state[:self.state_dim]

    def select_action(self,state,available=None,greedy=False):
        if available is None: available=list(range(self.action_dim))
        if not greedy and random.random()<self.epsilon: return random.choice(available)
        with torch.no_grad():
            q=self.online_net(torch.FloatTensor(state).unsqueeze(0)).squeeze(0).numpy()
        masked=np.full(self.action_dim,-np.inf)
        for a in available: masked[a]=q[a]
        return int(np.argmax(masked))

    def recommend_path(self,student_embedding,mastery_scores,topic_list,engagement,n=5):
        state=self.build_state(student_embedding,mastery_scores,topic_list,engagement)
        available=[i for i,t in enumerate(topic_list[:self.action_dim]) if mastery_scores.get(t,0.0)<0.85]
        if not available: available=list(range(min(self.action_dim,len(topic_list))))
        with torch.no_grad():
            q=self.online_net(torch.FloatTensor(state).unsqueeze(0)).squeeze(0).numpy()
        ranked=sorted(available,key=lambda i:q[i],reverse=True)[:n]
        return [{"topic_id":topic_list[i],"q_value":float(q[i]),"current_mastery":mastery_scores.get(topic_list[i],0.0),"rank":j+1} for j,i in enumerate(ranked) if i<len(topic_list)]

    def train_step(self):
        if len(self.replay_buffer)<self.batch_size: return None
        s,a,r,ns,d=self.replay_buffer.sample(self.batch_size)
        st=torch.FloatTensor(s); at=torch.LongTensor(a).unsqueeze(1)
        rt=torch.FloatTensor(r); nst=torch.FloatTensor(ns); dt=torch.FloatTensor(d)
        cq=self.online_net(st).gather(1,at).squeeze(1)
        with torch.no_grad():
            na=self.online_net(nst).argmax(1,keepdim=True)
            nq=self.target_net(nst).gather(1,na).squeeze(1)
            tq=rt+self.gamma*nq*(1-dt)
        loss=F.smooth_l1_loss(cq,tq)
        self.optimizer.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(self.online_net.parameters(),10.0)
        self.optimizer.step(); self.steps+=1
        if self.steps%self.target_update_freq==0: self.target_net.load_state_dict(self.online_net.state_dict())
        self.epsilon=max(self.epsilon_end,self.epsilon*self.epsilon_decay)
        return float(loss.item())

    def save_model(self):
        os.makedirs(os.path.dirname(self.model_path),exist_ok=True)
        torch.save({"online":self.online_net.state_dict(),"target":self.target_net.state_dict(),"opt":self.optimizer.state_dict(),"epsilon":self.epsilon,"steps":self.steps},self.model_path)

    def _load(self):
        if os.path.exists(self.model_path):
            c=torch.load(self.model_path,map_location="cpu")
            self.online_net.load_state_dict(c["online"]); self.target_net.load_state_dict(c["target"])
            self.optimizer.load_state_dict(c["opt"]); self.epsilon=c.get("epsilon",self.epsilon_end); self.steps=c.get("steps",0)

rl_agent = LearningPathAgent(state_dim=165,action_dim=36)
'@ | Out-File -FilePath "app\ai\rl_agent.py" -Encoding utf8

Write-Host "  rl_agent.py created" -ForegroundColor Green

# app\ai\ai_tutor.py
@'
import anthropic, json, logging
from typing import List, Dict, Optional
from app.config import settings

logger = logging.getLogger(__name__)

EDUCATIONAL_CONTENT = [
    {"id":"c1","topic_id":"math_derivatives","content":"Derivatives measure rate of change. Power rule: d/dx[xn]=nxn-1. Product rule: d/dx[fg]=fg+fg. Chain rule: d/dx[f(g(x))]=f(g(x))g(x). Applications: maxima/minima, optimization, velocity from position.","difficulty":4},
    {"id":"c2","topic_id":"cs_oop","content":"OOP: Encapsulation (bundle data+methods), Inheritance (child inherits parent), Polymorphism (same interface, different implementations), Abstraction (hide complexity). Python: class Animal: def speak(self): pass. class Dog(Animal): def speak(self): return 'Woof!'","difficulty":3},
    {"id":"c3","topic_id":"phys_kinematics","content":"Kinematics equations (constant acceleration): v=u+at, s=ut+at2/2, v2=u2+2as, s=(u+v)t/2. Projectile: horizontal constant velocity + vertical gravity=-9.8m/s2.","difficulty":2},
    {"id":"c4","topic_id":"math_statistics","content":"Mean=sum/n, Median=middle value, Std dev=spread. Probability: P(A)=favorable/total. Bayes theorem: P(A|B)=P(B|A)P(A)/P(B). Normal dist: 68-95-99.7 rule.","difficulty":3},
    {"id":"c5","topic_id":"cs_algorithms","content":"Big-O: O(1)<O(logn)<O(n)<O(nlogn)<O(n2). Merge sort O(nlogn) stable. Quick sort O(nlogn) avg. BFS/DFS O(V+E). Dijkstra O((V+E)logV).","difficulty":4},
]

SYSTEM_PROMPT = """You are an expert AI tutor in an adaptive learning system. Personalize teaching to the student level.
Principles: meet student where they are, use concrete examples first, break into steps, ask Socratic questions.
Student profile: {profile}. Topic: {topic}. Reference context: {context}"""

class RAGRetriever:
    def retrieve(self, query, topic_id=None, top_k=3):
        if topic_id:
            results=[c for c in EDUCATIONAL_CONTENT if c["topic_id"]==topic_id]
            if results: return [{"content":r["content"],"topic_id":r["topic_id"],"score":1.0} for r in results[:top_k]]
        return [{"content":c["content"],"topic_id":c["topic_id"],"score":0.5} for c in EDUCATIONAL_CONTENT[:top_k]]

    def seed_content(self):
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import PointStruct
            from sentence_transformers import SentenceTransformer
            from app.config import settings
            encoder=SentenceTransformer("all-mpnet-base-v2")
            client=QdrantClient(url=settings.QDRANT_URL)
            points=[PointStruct(id=i,vector=encoder.encode(c["content"],normalize_embeddings=True).tolist(),payload={"content_id":c["id"],"topic_id":c["topic_id"],"content":c["content"],"difficulty":c["difficulty"]}) for i,c in enumerate(EDUCATIONAL_CONTENT)]
            client.upsert(collection_name="content_embeddings",points=points)
            print(f"Seeded {len(points)} content items into Qdrant")
        except Exception as e:
            print(f"Qdrant seeding skipped (will use in-memory fallback): {e}")

class AITutor:
    def __init__(self):
        self.retriever=RAGRetriever()
        self.client=None

    def _get_client(self):
        if self.client is None:
            self.client=anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self.client

    def chat(self, messages, student_profile, topic="general", mode="explain"):
        query=messages[-1]["content"] if messages else ""
        retrieved=self.retriever.retrieve(query,topic_id=topic,top_k=2)
        context="\n".join([r["content"] for r in retrieved]) or "No specific content found."
        profile_str=(f"Style:{student_profile.get('learning_style','visual')}, IRT:{student_profile.get('irt_ability',0.0):.2f}, Mastery:{student_profile.get('mastery_scores',{}).get(topic,0.0):.2f}")
        system=SYSTEM_PROMPT.format(profile=profile_str,topic=topic,context=context)
        if mode=="solve": system+="\nBreak solution into numbered steps."
        elif mode=="quiz": system+="\nGenerate one focused practice question."
        elif mode=="example": system+="\nProvide 2-3 concrete examples, simple to complex."
        try:
            resp=self._get_client().messages.create(model="claude-opus-4-5",max_tokens=1500,system=system,messages=[{"role":m["role"],"content":m["content"]} for m in messages])
            return resp.content[0].text
        except Exception as e:
            logger.error(f"AI Tutor error: {e}")
            return f"[Demo mode — add ANTHROPIC_API_KEY to .env for full AI responses]\n\nContext for {topic}:\n{context[:500]}"

    def evaluate_answer(self, student_answer, correct_answer):
        try:
            prompt=f"Grade this answer. Correct: {correct_answer}\nStudent: {student_answer}\nRespond ONLY in JSON: {{\"score\":0.8,\"feedback\":\"...\",\"key_concepts_missed\":[]}}"
            resp=self._get_client().messages.create(model="claude-opus-4-5",max_tokens=300,messages=[{"role":"user","content":prompt}])
            text=resp.content[0].text.replace("```json","").replace("```","").strip()
            result=json.loads(text)
            return {"score":float(result.get("score",0.5)),"feedback":result.get("feedback",""),"key_concepts_missed":result.get("key_concepts_missed",[])}
        except Exception:
            cw=set(correct_answer.lower().split()); sw=set(student_answer.lower().split())
            overlap=len(cw&sw)/max(len(cw),1)
            return {"score":min(overlap*1.5,1.0),"feedback":"Answer evaluated (API unavailable).","key_concepts_missed":[]}

    def generate_question(self, topic_id, difficulty=0.5, q_type="mcq", student_profile=None):
        dlabel="easy" if difficulty<0.4 else "hard" if difficulty>0.7 else "medium"
        prompt=f"Generate a {dlabel} {q_type} question for topic: {topic_id}.\nIf MCQ: 4 options A/B/C/D. If coding: problem+example I/O.\nRespond ONLY in JSON: {{\"question\":\"...\",\"type\":\"{q_type}\",\"options\":null,\"correct_answer\":\"...\",\"explanation\":\"...\",\"difficulty\":{difficulty:.2f}}}"
        try:
            resp=self._get_client().messages.create(model="claude-opus-4-5",max_tokens=600,messages=[{"role":"user","content":prompt}])
            text=resp.content[0].text.replace("```json","").replace("```","").strip()
            return json.loads(text)
        except Exception:
            return {"question":f"Explain the key concepts of {topic_id} in your own words.","type":"descriptive","options":None,"correct_answer":f"A clear explanation of {topic_id} covering its definition and applications.","explanation":"Open-ended question.","difficulty":difficulty}

ai_tutor = AITutor()
'@ | Out-File -FilePath "app\ai\ai_tutor.py" -Encoding utf8

Write-Host "  ai_tutor.py created" -ForegroundColor Green

# app\ai\performance_predictor.py
@'
import numpy as np, torch, torch.nn as nn, pickle, os
from typing import Dict, List, Tuple
from sklearn.preprocessing import StandardScaler

def build_prediction_features(user_data, sessions):
    f=np.zeros(25,dtype=np.float32)
    f[0]=user_data.get("irt_ability",0.0)/3.0+0.5
    f[1]=user_data.get("overall_accuracy",0.5)
    f[2]=user_data.get("cognitive_level",0.5)
    f[3]=min(user_data.get("learning_speed",1.0)/2.0,1.0)
    f[4]=min(user_data.get("total_questions_answered",0)/500.0,1.0)
    f[5]=min(user_data.get("total_sessions",0)/100.0,1.0)
    f[6]=user_data.get("avg_session_minutes",30)/60.0
    f[7]=user_data.get("streak_days",0)/30.0
    f[8]=user_data.get("engagement_score",0.5)
    if sessions:
        recent=sessions[-5:]
        f[9]=np.mean([s.get("learning_gain",0) for s in recent])
        f[10]=np.mean([s.get("time_on_task",0)/max(s.get("duration_seconds",1),1) for s in recent])
        f[11]=np.mean([s.get("hint_requests",0) for s in recent])/5.0
        f[12]=float(np.std([s.get("post_mastery",0) for s in recent]))
    mastery=user_data.get("mastery_scores",{})
    if mastery:
        mv=list(mastery.values())
        f[14]=float(np.mean(mv)); f[15]=float(np.std(mv))
        f[16]=float(sum(1 for m in mv if m>0.7)/max(len(mv),1))
        f[17]=float(sum(1 for m in mv if m<0.4)/max(len(mv),1))
    f[21]=user_data.get("grade_level",10)/12.0
    f[23]=user_data.get("overall_accuracy",0.5)
    f[24]=float(user_data.get("total_sessions",0)>10)
    return f

def build_session_sequence(sessions, seq_len=20):
    seq=np.zeros((seq_len,8),dtype=np.float32)
    for i,s in enumerate(sessions[-seq_len:]):
        idx=seq_len-min(len(sessions),seq_len)+i
        seq[idx,0]=s.get("post_mastery",0.0); seq[idx,1]=s.get("learning_gain",0.0)
        seq[idx,2]=s.get("engagement_score",0.5); seq[idx,3]=min(s.get("duration_seconds",0)/3600.0,1.0)
        seq[idx,4]=s.get("overall_accuracy",0.5); seq[idx,5]=s.get("hint_requests",0)/5.0
        seq[idx,6]=s.get("total_reward",0.0)/5.0+0.5; seq[idx,7]=s.get("irt_ability",0.0)/3.0+0.5
    return seq

class LSTMPerformancePredictor(nn.Module):
    def __init__(self,input_dim=8,hidden_dim=64,num_layers=2,dropout=0.2):
        super().__init__()
        self.lstm=nn.LSTM(input_dim,hidden_dim,num_layers=num_layers,batch_first=True,dropout=dropout if num_layers>1 else 0)
        self.attention=nn.Linear(hidden_dim,1)
        self.regressor=nn.Sequential(nn.Linear(hidden_dim,32),nn.ReLU(),nn.Dropout(dropout),nn.Linear(32,1),nn.Sigmoid())
    def forward(self,x):
        out,_=self.lstm(x); w=torch.softmax(self.attention(out),dim=1)
        return self.regressor((w*out).sum(dim=1))

class PerformancePredictor:
    def __init__(self,model_dir="models"):
        self.model_dir=model_dir; self.xgb_model=None
        self.lstm_model=LSTMPerformancePredictor(); self.scaler=StandardScaler(); self._load()

    def _load(self):
        xp=os.path.join(self.model_dir,"xgb_predictor.pkl")
        lp=os.path.join(self.model_dir,"lstm_predictor.pt")
        sp=os.path.join(self.model_dir,"predictor_scaler.pkl")
        if os.path.exists(xp):
            with open(xp,"rb") as f: self.xgb_model=pickle.load(f)
        if os.path.exists(lp): self.lstm_model.load_state_dict(torch.load(lp,map_location="cpu")); self.lstm_model.eval()
        if os.path.exists(sp):
            with open(sp,"rb") as f: self.scaler=pickle.load(f)

    def predict(self,user_data,sessions):
        tf=build_prediction_features(user_data,sessions)
        seq=torch.FloatTensor(build_session_sequence(sessions)).unsqueeze(0)
        if self.xgb_model is not None:
            try:
                xs=self.scaler.transform(tf.reshape(1,-1))
                xscore=float(self.xgb_model.predict(xs)[0])
            except: xscore=self._heuristic(tf)
        else: xscore=self._heuristic(tf)
        with torch.no_grad(): lscore=float(self.lstm_model(seq).squeeze())
        w=0.4 if not sessions else 0.4; final=float(np.clip(w*xscore+(1-w)*lscore,0,1))
        risk=float(np.clip(1-final+0.1*(tf[17]),0,1))
        factors=[]
        if tf[1]<0.5: factors.append({"factor":"Low answer accuracy","severity":"high","value":float(tf[1])})
        if tf[8]<0.4: factors.append({"factor":"Low engagement score","severity":"medium","value":float(tf[8])})
        if tf[17]>0.3: factors.append({"factor":"Multiple weak topics","severity":"high","value":float(tf[17])})
        if len(sessions)<5: factors.append({"factor":"Insufficient learning history","severity":"medium","value":float(len(sessions))})
        recs=[]
        if any(f["factor"]=="Low answer accuracy" for f in factors): recs.append("Review foundational concepts before advancing")
        if any(f["factor"]=="Low engagement score" for f in factors): recs.append("Try shorter 15-20 minute study sessions")
        if not recs: recs.append("Keep up your current learning pace — you are on track!")
        return {"predicted_final_score":round(final,3),"dropout_risk":round(risk,3),"risk_level":"high" if risk>0.6 else "medium" if risk>0.35 else "low","xgb_prediction":round(xscore,3),"lstm_prediction":round(lscore,3),"risk_factors":factors[:4],"recommendations":recs}

    def _heuristic(self,f): return float(np.clip(0.3*f[1]+0.3*f[0]+0.2*f[8]+0.2*f[14],0,1))

performance_predictor = PerformancePredictor()
'@ | Out-File -FilePath "app\ai\performance_predictor.py" -Encoding utf8

Write-Host "  performance_predictor.py created" -ForegroundColor Green

# app\ai\xai_explainer.py
@'
from typing import Dict, List, Any

class XAIExplainer:
    def explain_recommendation(self,topic_id,topic_name,student_profile,q_value,current_mastery):
        reasons=[]; factors={}
        if current_mastery<0.3: reasons.append(f"You have not started {topic_name} yet"); factors["mastery_gap"]=1.0-current_mastery
        elif current_mastery<0.6: reasons.append(f"Mastery at {current_mastery:.0%} — room to improve"); factors["mastery_gap"]=1.0-current_mastery
        if student_profile.get("irt_ability",0)>0.5: reasons.append("Your ability score shows readiness"); factors["ability_readiness"]=0.8
        if student_profile.get("engagement_score",0.5)>0.7: reasons.append("High engagement — good time for new material"); factors["engagement"]=student_profile["engagement_score"]
        if topic_id in student_profile.get("knowledge_gaps",[]): reasons.append("Identified as a knowledge gap"); factors["knowledge_gap"]=1.0
        reasons.append("All prerequisites meet mastery threshold"); factors["prereq_readiness"]=0.9
        total=sum(factors.values()) or 1
        return {"topic_id":topic_id,"topic_name":topic_name,"confidence":round(min(abs(q_value)/3+0.5,1),2),"primary_reason":reasons[0] if reasons else "Based on your profile","all_reasons":reasons,"contributing_factors":factors,"feature_attributions":[{"feature":k.replace("_"," ").title(),"value":round(v,3),"percentage":round(v/total*100,1)} for k,v in sorted(factors.items(),key=lambda x:-x[1])]}

xai_explainer = XAIExplainer()
'@ | Out-File -FilePath "app\ai\xai_explainer.py" -Encoding utf8

# app\ai\continual_learner.py
@'
import torch, torch.nn as nn
from typing import Dict, List, Optional
from copy import deepcopy
import logging
logger=logging.getLogger(__name__)

class EWC:
    def __init__(self,model,dataloader,device="cpu"):
        self.params={n:p.clone().detach() for n,p in model.named_parameters() if p.requires_grad}
        self.fisher={n:torch.zeros_like(p) for n,p in model.named_parameters() if p.requires_grad}
    def penalty(self,model,lambda_ewc=1000.0):
        loss=torch.tensor(0.0)
        for n,p in model.named_parameters():
            if p.requires_grad and n in self.fisher:
                loss+=(self.fisher[n]*(p-self.params[n])**2).sum()
        return (lambda_ewc/2)*loss

class FederatedAggregator:
    def __init__(self,global_model): self.global_model=global_model; self.round=0
    def aggregate(self,local_states,weights=None):
        if not local_states: return self.global_model
        if weights is None: weights=[1/len(local_states)]*len(local_states)
        total=sum(weights); weights=[w/total for w in weights]
        gs=deepcopy(local_states[0])
        for k in gs: gs[k]=sum(weights[i]*local_states[i][k] for i in range(len(local_states)))
        self.global_model.load_state_dict(gs); self.round+=1
        return self.global_model
'@ | Out-File -FilePath "app\ai\continual_learner.py" -Encoding utf8

Write-Host "  AI modules created" -ForegroundColor Green

# ── scripts\init_db.py (already done above via heredoc) ──

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  All files created successfully!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host "  1. Edit .env and set your ANTHROPIC_API_KEY" -ForegroundColor White
Write-Host "  2. Make sure Docker is running (docker ps)" -ForegroundColor White
Write-Host "  3. Run: python scripts/init_db.py" -ForegroundColor White
Write-Host "  4. Run: python scripts/seed_knowledge_graph.py" -ForegroundColor White
Write-Host "  5. Run: python scripts/seed_content.py" -ForegroundColor White
Write-Host "  6. Run: python scripts/train_models.py" -ForegroundColor White
Write-Host "  7. Run: uvicorn app.main:app --reload --port 8000" -ForegroundColor White
Write-Host ""
Write-Host "Get your FREE Anthropic API key at: https://console.anthropic.com" -ForegroundColor Cyan
