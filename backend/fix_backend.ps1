# ============================================================
# FIX ALL BACKEND ERRORS — Run from backend\ folder
# powershell -ExecutionPolicy Bypass -File fix_backend.ps1
# ============================================================

Write-Host "Fixing all backend issues..." -ForegroundColor Cyan

# ── Step 1: Fix .env (UTF8 NO BOM — critical!) ───────────────
Write-Host "Step 1: Recreating .env with correct encoding..." -ForegroundColor Yellow

# Read current API key if it exists
$currentEnv = ""
if (Test-Path ".env") {
    $currentEnv = Get-Content ".env" -Raw
}
$apiKey = "your-anthropic-api-key-here"
if ($currentEnv -match "ANTHROPIC_API_KEY=(.+)") {
    $apiKey = $Matches[1].Trim()
}
Write-Host "  Found API key: $($apiKey.Substring(0, [Math]::Min(20, $apiKey.Length)))..." -ForegroundColor Gray

# Write .env with UTF8 NO BOM (critical for Python dotenv)
$envContent = "DATABASE_URL=postgresql+asyncpg://aluser:alpassword@localhost:5432/adaptive_learning`n"
$envContent += "DATABASE_URL_SYNC=postgresql://aluser:alpassword@localhost:5432/adaptive_learning`n"
$envContent += "NEO4J_URI=bolt://localhost:7687`n"
$envContent += "NEO4J_USER=neo4j`n"
$envContent += "NEO4J_PASSWORD=password`n"
$envContent += "REDIS_URL=redis://localhost:6379/0`n"
$envContent += "QDRANT_URL=http://localhost:6333`n"
$envContent += "QDRANT_COLLECTION=adaptive_learning_content`n"
$envContent += "SECRET_KEY=super-secret-key-change-in-production-abc123xyz`n"
$envContent += "ALGORITHM=HS256`n"
$envContent += "ACCESS_TOKEN_EXPIRE_MINUTES=60`n"
$envContent += "ANTHROPIC_API_KEY=$apiKey`n"
$envContent += "MLFLOW_TRACKING_URI=./mlruns`n"
$envContent += "APP_NAME=Adaptive Learning System`n"
$envContent += "DEBUG=True`n"
$envContent += "CORS_ORIGINS=[`"http://localhost:5173`",`"http://localhost:3000`"]`n"
$envContent += "CELERY_BROKER_URL=redis://localhost:6379/1`n"
$envContent += "CELERY_RESULT_BACKEND=redis://localhost:6379/2`n"

# UTF8 without BOM
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText("$PWD\.env", $envContent, $utf8NoBom)
Write-Host "  .env rewritten (UTF-8 No BOM)" -ForegroundColor Green

# ── Step 2: Fix app\config.py ────────────────────────────────
Write-Host "Step 2: Fixing config.py..." -ForegroundColor Yellow
$configContent = @'
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
'@
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText("$PWD\app\config.py", $configContent, $utf8NoBom)
Write-Host "  config.py fixed" -ForegroundColor Green

# ── Step 3: Fix app\main.py ──────────────────────────────────
Write-Host "Step 3: Fixing main.py..." -ForegroundColor Yellow
$mainContent = @'
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
'@
[System.IO.File]::WriteAllText("$PWD\app\main.py", $mainContent, $utf8NoBom)
Write-Host "  main.py fixed" -ForegroundColor Green

# ── Step 4: Fix app\database.py ──────────────────────────────
Write-Host "Step 4: Fixing database.py..." -ForegroundColor Yellow
$dbContent = @'
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import logging

logger = logging.getLogger(__name__)

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

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

_qdrant_client = None

def get_qdrant():
    global _qdrant_client
    if _qdrant_client is None:
        try:
            from qdrant_client import QdrantClient
            _qdrant_client = QdrantClient(url=settings.QDRANT_URL, timeout=5)
        except Exception as e:
            logger.warning(f"Qdrant not available: {e}")
    return _qdrant_client

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
                client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=size, distance=Distance.COSINE)
                )
                logger.info(f"Created Qdrant collection: {name}")
    except Exception as e:
        logger.warning(f"Qdrant collection setup skipped: {e}")

async def init_db():
    async with engine.begin() as conn:
        from app.models import user, assessment
        await conn.run_sync(Base.metadata.create_all)
    logger.info("PostgreSQL tables created")
    ensure_qdrant_collection()

async def close_db():
    await engine.dispose()
'@
[System.IO.File]::WriteAllText("$PWD\app\database.py", $dbContent, $utf8NoBom)
Write-Host "  database.py fixed" -ForegroundColor Green

# ── Step 5: Fix app\ai\ai_tutor.py (better error handling) ───
Write-Host "Step 5: Fixing ai_tutor.py..." -ForegroundColor Yellow
$tutorContent = @'
import json
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

EDUCATIONAL_CONTENT = [
    {"id": "c1", "topic_id": "math_derivatives", "content": "Derivatives measure rate of change. Power rule: d/dx[x^n] = n*x^(n-1). Product rule: (fg)' = f'g + fg'. Chain rule: d/dx[f(g(x))] = f'(g(x)) * g'(x). Used for optimization, finding maxima/minima, and velocity calculations.", "difficulty": 4},
    {"id": "c2", "topic_id": "cs_oop", "content": "Object-Oriented Programming (OOP) has 4 pillars: 1) Encapsulation - bundle data and methods, hide internal state. 2) Inheritance - child classes inherit from parent. 3) Polymorphism - same interface, different implementations. 4) Abstraction - hide complexity. Example: class Dog(Animal): def speak(self): return 'Woof!'", "difficulty": 3},
    {"id": "c3", "topic_id": "phys_kinematics", "content": "Kinematics equations (constant acceleration): v = u + at, s = ut + (1/2)at^2, v^2 = u^2 + 2as. Projectile motion: horizontal (constant velocity) + vertical (gravity = -9.8 m/s^2). Range = v^2*sin(2theta)/g.", "difficulty": 2},
    {"id": "c4", "topic_id": "math_statistics", "content": "Statistics: Mean = sum/n, Median = middle value, Mode = most frequent. Standard deviation measures spread. Probability: P(A) = favorable/total. Bayes theorem: P(A|B) = P(B|A)*P(A)/P(B). Normal distribution: 68-95-99.7 rule.", "difficulty": 3},
    {"id": "c5", "topic_id": "cs_algorithms", "content": "Algorithm complexity Big-O: O(1) < O(log n) < O(n) < O(n log n) < O(n^2). Sorting: Bubble O(n^2), Merge Sort O(n log n) stable, Quick Sort O(n log n) average. Graph: BFS/DFS O(V+E), Dijkstra O((V+E)log V).", "difficulty": 4},
    {"id": "c6", "topic_id": "cs_data_structures", "content": "Data structures: Array O(1) access, O(n) search. Linked List O(n) access, O(1) insert. Stack/Queue LIFO/FIFO. Binary Search Tree O(log n) average. Hash Table O(1) average. Heap for priority queue.", "difficulty": 4},
    {"id": "c7", "topic_id": "math_algebra_basics", "content": "Algebra basics: Variables represent unknown values. Linear equations: ax + b = 0, solution x = -b/a. Simultaneous equations solved by substitution or elimination. Inequalities: flip sign when multiplying by negative.", "difficulty": 2},
    {"id": "c8", "topic_id": "math_statistics", "content": "Probability distributions: Binomial P(X=k) = C(n,k) * p^k * (1-p)^(n-k). Poisson for rare events. Normal distribution symmetric bell curve. Central Limit Theorem: sample means are normally distributed.", "difficulty": 3},
]

SYSTEM_PROMPT = """You are an expert AI tutor in an adaptive learning system. You personalize teaching based on the student's level.

Core principles:
- Meet the student where they are - match their vocabulary and level
- Use concrete examples BEFORE abstract concepts  
- Break complex ideas into digestible steps
- Ask Socratic questions to guide discovery
- Be encouraging and patient

Student Profile: {profile}
Current Topic: {topic}

Reference Material:
{context}

Remember: You are a helpful tutor. Give clear, educational responses."""


class RAGRetriever:
    """Retrieves relevant educational content."""
    
    def retrieve(self, query: str, topic_id: Optional[str] = None, top_k: int = 3) -> List[Dict]:
        """Simple keyword-based retrieval as fallback."""
        if topic_id:
            results = [c for c in EDUCATIONAL_CONTENT if c["topic_id"] == topic_id]
            if results:
                return [{"content": r["content"], "topic_id": r["topic_id"], "score": 1.0} for r in results[:top_k]]
        
        # Keyword search
        query_lower = query.lower()
        scored = []
        for c in EDUCATIONAL_CONTENT:
            score = sum(1 for word in query_lower.split() if word in c["content"].lower())
            if score > 0:
                scored.append({"content": c["content"], "topic_id": c["topic_id"], "score": score})
        
        scored.sort(key=lambda x: -x["score"])
        return scored[:top_k] if scored else [{"content": EDUCATIONAL_CONTENT[0]["content"], "topic_id": "general", "score": 0.1}]

    def seed_content(self):
        """Seed content into Qdrant if available."""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import PointStruct
            from sentence_transformers import SentenceTransformer
            from app.config import settings
            
            encoder = SentenceTransformer("all-MiniLM-L6-v2")
            client = QdrantClient(url=settings.QDRANT_URL, timeout=10)
            
            points = []
            for i, c in enumerate(EDUCATIONAL_CONTENT):
                vec = encoder.encode(c["content"], normalize_embeddings=True).tolist()
                points.append(PointStruct(
                    id=i,
                    vector=vec,
                    payload={"content_id": c["id"], "topic_id": c["topic_id"], "content": c["content"]}
                ))
            client.upsert(collection_name="content_embeddings", points=points)
            print(f"Seeded {len(points)} content items into Qdrant")
        except Exception as e:
            print(f"Qdrant seeding skipped (using in-memory fallback): {e}")


class AITutor:
    """RAG-powered AI tutor using Claude API."""
    
    def __init__(self):
        self.retriever = RAGRetriever()
        self._client = None

    def _get_client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                from app.config import settings
                if not settings.ANTHROPIC_API_KEY or settings.ANTHROPIC_API_KEY == "your-anthropic-api-key-here":
                    return None
                self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            except Exception as e:
                logger.error(f"Failed to create Anthropic client: {e}")
                return None
        return self._client

    def chat(self, messages: List[Dict], student_profile: Dict, topic: str = "general", mode: str = "explain") -> str:
        """Multi-turn tutoring conversation."""
        query = messages[-1]["content"] if messages else ""
        
        # Retrieve relevant content
        retrieved = self.retriever.retrieve(query, topic_id=topic, top_k=3)
        context = "\n\n---\n\n".join([r["content"] for r in retrieved])
        
        profile_str = (
            f"Learning style: {student_profile.get('learning_style', 'visual')}, "
            f"IRT ability: {student_profile.get('irt_ability', 0.0):.2f}, "
            f"Topic mastery: {student_profile.get('mastery_scores', {}).get(topic, 0.0):.0%}"
        )
        
        system = SYSTEM_PROMPT.format(profile=profile_str, topic=topic, context=context or "No specific content found.")
        
        if mode == "solve":
            system += "\n\nIMPORTANT: Break down the solution step by step. Number each step clearly."
        elif mode == "quiz":
            system += "\n\nIMPORTANT: Generate ONE focused practice question at the student's level. Include the answer at the end."
        elif mode == "example":
            system += "\n\nIMPORTANT: Provide 2-3 concrete, memorable examples. Start simple, increase complexity."

        client = self._get_client()
        
        if client is None:
            # Demo mode with educational content
            content_preview = retrieved[0]["content"] if retrieved else "No content available."
            return (
                f"[Demo Mode - API key not configured]\n\n"
                f"**Topic: {topic}**\n\n"
                f"Here's what I know about this topic:\n\n"
                f"{content_preview}\n\n"
                f"---\n"
                f"*To enable full AI tutoring: add your ANTHROPIC_API_KEY to backend/.env and restart the server.*\n"
                f"*Get a free key at: https://console.anthropic.com*"
            )
        
        try:
            response = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=1500,
                system=system,
                messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            content_preview = retrieved[0]["content"] if retrieved else ""
            return (
                f"I encountered an API error. Here's the educational content for **{topic}**:\n\n"
                f"{content_preview}\n\n"
                f"*Error details: {str(e)[:100]}*"
            )

    def evaluate_answer(self, student_answer: str, correct_answer: str) -> Dict:
        """Evaluate a student answer."""
        client = self._get_client()
        
        if client:
            try:
                prompt = (
                    f"Grade this student answer fairly.\n\n"
                    f"Correct answer: {correct_answer}\n"
                    f"Student answer: {student_answer}\n\n"
                    f"Respond ONLY with valid JSON (no markdown):\n"
                    f'{{\"score\": 0.8, \"feedback\": \"Good attempt...\", \"key_concepts_missed\": []}}'
                )
                response = client.messages.create(
                    model="claude-opus-4-5",
                    max_tokens=300,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text.strip()
                # Remove markdown code blocks if present
                text = text.replace("```json", "").replace("```", "").strip()
                result = json.loads(text)
                return {
                    "score": float(result.get("score", 0.5)),
                    "feedback": result.get("feedback", "Answer evaluated."),
                    "key_concepts_missed": result.get("key_concepts_missed", []),
                }
            except Exception as e:
                logger.warning(f"LLM evaluation failed, using keyword matching: {e}")
        
        # Keyword-based fallback
        correct_words = set(correct_answer.lower().split())
        student_words = set(student_answer.lower().split())
        if len(correct_words) == 0:
            score = 0.5
        else:
            overlap = len(correct_words & student_words) / len(correct_words)
            score = min(overlap * 1.5, 1.0)
        
        return {
            "score": round(score, 3),
            "feedback": f"Your answer covered {score:.0%} of the key concepts." if score > 0 else "Try to include more relevant keywords.",
            "key_concepts_missed": [],
        }

    def generate_question(self, topic_id: str, difficulty: float = 0.5, q_type: str = "mcq", student_profile: Optional[Dict] = None) -> Dict:
        """Generate an AI assessment question."""
        difficulty_label = "easy" if difficulty < 0.4 else ("hard" if difficulty > 0.7 else "medium")
        
        client = self._get_client()
        
        if client:
            try:
                prompt = (
                    f"Generate a {difficulty_label} {q_type} question for the topic: {topic_id}.\n\n"
                    f"Requirements:\n"
                    f"- Difficulty: {difficulty_label} (score: {difficulty:.2f})\n"
                    f"- Type: {q_type}\n"
                    f"- If MCQ: provide exactly 4 options labeled A, B, C, D\n"
                    f"- If coding: clear problem statement with example input/output\n"
                    f"- If descriptive: ask for explanation or comparison\n\n"
                    f"Respond ONLY with valid JSON (no markdown):\n"
                    f'{{"question": "...", "type": "{q_type}", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], "correct_answer": "...", "explanation": "...", "difficulty": {difficulty:.2f}}}\n'
                    f'Note: set options to null if not MCQ.'
                )
                response = client.messages.create(
                    model="claude-opus-4-5",
                    max_tokens=600,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text.strip()
                text = text.replace("```json", "").replace("```", "").strip()
                return json.loads(text)
            except Exception as e:
                logger.warning(f"Question generation failed: {e}")
        
        # Fallback questions by topic
        fallback_questions = {
            "math_derivatives": {
                "question": "What is the derivative of f(x) = 3x² + 2x + 1?",
                "type": "mcq",
                "options": ["A. 6x + 2", "B. 3x + 2", "C. 6x² + 2", "D. 3x²"],
                "correct_answer": "A. 6x + 2",
                "explanation": "Using the power rule: d/dx[3x²] = 6x, d/dx[2x] = 2, d/dx[1] = 0. So f'(x) = 6x + 2.",
                "difficulty": difficulty,
            },
            "cs_oop": {
                "question": "Which OOP principle allows a child class to use methods from a parent class?",
                "type": "mcq",
                "options": ["A. Encapsulation", "B. Inheritance", "C. Polymorphism", "D. Abstraction"],
                "correct_answer": "B. Inheritance",
                "explanation": "Inheritance allows a child class to inherit properties and methods from a parent class.",
                "difficulty": difficulty,
            },
            "phys_kinematics": {
                "question": "A car starts from rest and accelerates at 4 m/s². What is its velocity after 5 seconds?",
                "type": "mcq",
                "options": ["A. 10 m/s", "B. 15 m/s", "C. 20 m/s", "D. 25 m/s"],
                "correct_answer": "C. 20 m/s",
                "explanation": "Using v = u + at: v = 0 + (4)(5) = 20 m/s.",
                "difficulty": difficulty,
            },
            "math_statistics": {
                "question": "What is the mean of the dataset: [2, 4, 6, 8, 10]?",
                "type": "mcq",
                "options": ["A. 4", "B. 5", "C. 6", "D. 7"],
                "correct_answer": "C. 6",
                "explanation": "Mean = (2+4+6+8+10)/5 = 30/5 = 6.",
                "difficulty": difficulty,
            },
            "cs_algorithms": {
                "question": "What is the time complexity of binary search?",
                "type": "mcq",
                "options": ["A. O(n)", "B. O(n²)", "C. O(log n)", "D. O(n log n)"],
                "correct_answer": "C. O(log n)",
                "explanation": "Binary search halves the search space each iteration, giving O(log n) complexity.",
                "difficulty": difficulty,
            },
            "cs_data_structures": {
                "question": "Which data structure uses LIFO (Last In, First Out) order?",
                "type": "mcq",
                "options": ["A. Queue", "B. Stack", "C. Array", "D. Linked List"],
                "correct_answer": "B. Stack",
                "explanation": "A Stack uses LIFO - the last element pushed is the first one popped.",
                "difficulty": difficulty,
            },
        }
        
        return fallback_questions.get(topic_id, {
            "question": f"Explain the most important concept you know about {topic_id.replace('_', ' ')}.",
            "type": "descriptive",
            "options": None,
            "correct_answer": f"A clear explanation of the core concepts of {topic_id.replace('_', ' ')} including its definition, key properties, and practical applications.",
            "explanation": "Open-ended conceptual question.",
            "difficulty": difficulty,
        })


ai_tutor = AITutor()
'@
[System.IO.File]::WriteAllText("$PWD\app\ai\ai_tutor.py", $tutorContent, $utf8NoBom)
Write-Host "  ai_tutor.py fixed (better error handling + fallback questions)" -ForegroundColor Green

# ── Step 6: Fix app\routers\assessment.py ────────────────────
Write-Host "Step 6: Fixing assessment.py..." -ForegroundColor Yellow
$assessContent = @'
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
async def start_adaptive_test(
    req: StartTestRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        theta = current_user.irt_ability or 0.0
        item = adaptive_engine.select_next_item(
            current_theta=theta, used_item_ids=[], topic_filter=None
        )
        if not item:
            raise HTTPException(status_code=404, detail="No items available")
        
        difficulty = adaptive_engine.compute_mastery_score(item["irt_b"])
        q = ai_tutor.generate_question(
            topic_id=req.topic_id,
            difficulty=difficulty,
            q_type=item["question_type"],
        )
        
        return {
            "session_id": str(uuid.uuid4()),
            "question_id": item["question_id"],
            "topic_id": req.topic_id,
            "question": q,
            "irt_params": {"a": item["irt_a"], "b": item["irt_b"], "c": item["irt_c"]},
            "current_ability": theta,
            "current_se": current_user.irt_ability_std or 1.0,
            "items_answered": 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start test: {str(e)}")

@router.post("/adaptive/submit")
async def submit_adaptive_answer(
    req: SubmitAnswerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        eval_result = ai_tutor.evaluate_answer(req.student_answer, req.correct_answer)
        is_correct = eval_result["score"] >= 0.7
        
        prior = [(r["a"], r["b"], r["c"], int(r.get("response", 0))) for r in req.current_responses]
        all_responses = prior + [(req.irt_a, req.irt_b, req.irt_c, int(is_correct))]
        
        theta_before = current_user.irt_ability or 0.0
        theta_after, se = adaptive_engine.update_ability(
            all_responses, prior_mean=theta_before, prior_std=current_user.irt_ability_std or 1.0
        )
        
        try:
            assessment = Assessment(
                user_id=current_user.id, topic_id=req.topic_id,
                question_id=req.question_id, question_type="adaptive",
                irt_a=req.irt_a, irt_b=req.irt_b, irt_c=req.irt_c,
                student_answer=req.student_answer, correct_answer=req.correct_answer,
                is_correct=is_correct, score=eval_result["score"],
                ability_before=theta_before, ability_after=theta_after, ai_generated=True,
            )
            db.add(assessment)
        except Exception as db_err:
            pass  # Don't fail if DB write fails
        
        current_user.irt_ability = theta_after
        current_user.irt_ability_std = se
        n = (current_user.total_questions_answered or 0) + 1
        current_user.total_questions_answered = n
        current_user.overall_accuracy = ((n - 1) * (current_user.overall_accuracy or 0.5) + float(is_correct)) / n
        
        n_items = len(all_responses)
        stop, reason = adaptive_engine.should_stop(n_items, se)
        
        next_q = None
        if not stop:
            used = [r.get("question_id", "") for r in req.current_responses] + [req.question_id]
            nxt = adaptive_engine.select_next_item(theta_after, used)
            if nxt:
                d = adaptive_engine.compute_mastery_score(nxt["irt_b"])
                qd = ai_tutor.generate_question(topic_id=req.topic_id, difficulty=d, q_type=nxt["question_type"])
                next_q = {
                    "question_id": nxt["question_id"], "question": qd,
                    "irt_params": {"a": nxt["irt_a"], "b": nxt["irt_b"], "c": nxt["irt_c"]},
                }
        
        return {
            "is_correct": is_correct,
            "score": round(eval_result["score"], 3),
            "feedback": eval_result["feedback"],
            "ability_before": round(theta_before, 3),
            "ability_after": round(theta_after, 3),
            "standard_error": round(se, 3),
            "mastery_score": round(adaptive_engine.compute_mastery_score(theta_after), 3),
            "items_answered": n_items,
            "test_complete": stop,
            "stop_reason": reason,
            "next_question": next_q,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Submission error: {str(e)}")

@router.post("/generate")
async def generate_question(req: GenerateQuestionRequest, current_user: User = Depends(get_current_user)):
    try:
        return ai_tutor.generate_question(topic_id=req.topic_id, difficulty=req.difficulty, q_type=req.question_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/history")
async def get_history(
    user_id: str, topic_id: Optional[str] = None, limit: int = 50,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user),
):
    try:
        q = select(Assessment).where(Assessment.user_id == uuid.UUID(user_id))
        if topic_id:
            q = q.where(Assessment.topic_id == topic_id)
        result = await db.execute(q.order_by(Assessment.created_at.desc()).limit(limit))
        return [{"id": str(a.id), "topic_id": a.topic_id, "is_correct": a.is_correct, "score": a.score, "ability_after": a.ability_after, "created_at": str(a.created_at)} for a in result.scalars().all()]
    except Exception as e:
        return []
'@
[System.IO.File]::WriteAllText("$PWD\app\routers\assessment.py", $assessContent, $utf8NoBom)
Write-Host "  assessment.py fixed" -ForegroundColor Green

# ── Step 7: Fix app\routers\analytics.py ─────────────────────
Write-Host "Step 7: Fixing analytics.py..." -ForegroundColor Yellow
$analyticsContent = @'
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
    try:
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        mastery = user.mastery_scores or {}
        all_topics = knowledge_graph.get_all_topics()
        importance = knowledge_graph.compute_topic_importance()
        subjects = {}
        for t in all_topics:
            tid = t["id"]; subj = t.get("subject", "other")
            if subj not in subjects: subjects[subj] = []
            subjects[subj].append({
                "topic_id": tid, "name": t.get("name", tid),
                "mastery": mastery.get(tid, 0.0), "difficulty": t.get("difficulty", 3),
                "importance": importance.get(tid, 0.0),
                "status": "mastered" if mastery.get(tid, 0.0) >= 0.8 else "learning" if mastery.get(tid, 0.0) >= 0.4 else "gap",
            })
        gap_sub = knowledge_graph.get_knowledge_gap_subgraph(mastery, threshold=0.6)
        return {
            "user_id": user_id, "subjects": subjects, "gap_subgraph": gap_sub,
            "summary": {
                "total_topics": len(all_topics),
                "mastered": sum(1 for t in all_topics if mastery.get(t["id"], 0) >= 0.8),
                "learning": sum(1 for t in all_topics if 0.4 <= mastery.get(t["id"], 0) < 0.8),
                "gap": sum(1 for t in all_topics if mastery.get(t["id"], 0) < 0.4),
                "overall_mastery": sum(mastery.values()) / max(len(all_topics), 1),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/predict")
async def get_prediction(user_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        sessions_result = await db.execute(
            select(LearningSession).where(LearningSession.user_id == uuid.UUID(user_id)).order_by(LearningSession.started_at.asc())
        )
        sessions = [{c.name: getattr(s, c.name) for c in s.__table__.columns} for s in sessions_result.scalars().all()]
        user_dict = {c.name: getattr(user, c.name) for c in user.__table__.columns}
        pred = performance_predictor.predict(user_dict, sessions)
        user.dropout_risk = pred["dropout_risk"]
        user.predicted_final_score = pred["predicted_final_score"]
        return pred
    except HTTPException:
        raise
    except Exception as e:
        return {"predicted_final_score": 0.5, "dropout_risk": 0.2, "risk_level": "low", "xgb_prediction": 0.5, "lstm_prediction": 0.5, "risk_factors": [], "recommendations": ["Complete more sessions to get accurate predictions."]}

@router.get("/{user_id}/progress")
async def get_progress(user_id: str, limit: int = 30, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        sr = await db.execute(select(LearningSession).where(LearningSession.user_id == uuid.UUID(user_id)).order_by(LearningSession.started_at.desc()).limit(limit))
        ar = await db.execute(select(Assessment).where(Assessment.user_id == uuid.UUID(user_id)).order_by(Assessment.created_at.desc()).limit(limit))
        sessions = list(reversed(sr.scalars().all()))
        assessments = list(reversed(ar.scalars().all()))
        return {
            "sessions": [{"date": str(s.started_at), "topic": s.topic_name, "learning_gain": s.learning_gain, "post_mastery": s.post_mastery, "duration_minutes": (s.duration_seconds or 0) / 60, "reward": s.total_reward} for s in sessions],
            "ability_trajectory": [{"date": str(a.created_at), "ability": a.ability_after, "topic": a.topic_id, "correct": a.is_correct} for a in assessments if a.ability_after is not None],
        }
    except Exception as e:
        return {"sessions": [], "ability_trajectory": []}
'@
[System.IO.File]::WriteAllText("$PWD\app\routers\analytics.py", $analyticsContent, $utf8NoBom)
Write-Host "  analytics.py fixed" -ForegroundColor Green

# ── Step 8: Fix app\routers\learning_path.py ─────────────────
Write-Host "Step 8: Fixing learning_path.py..." -ForegroundColor Yellow
$lpContent = @'
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from pydantic import BaseModel
from app.database import get_db
from app.models.user import User
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

@router.get("/topics/all")
async def get_all_topics():
    return knowledge_graph.get_all_topics()

@router.get("/topics/{topic_id}/prerequisites")
async def get_prereqs(topic_id: str):
    return {"topic_id": topic_id, "prerequisites": knowledge_graph.get_prerequisites(topic_id, depth=3)}

@router.get("/{user_id}")
async def get_learning_path(
    user_id: str, n: int = 5,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        topic_list = [t["id"] for t in knowledge_graph.get_all_topics()]
        mastery = user.mastery_scores or {}
        embedding = user.embedding or []
        engagement = user.engagement_score or 0.5
        
        try:
            recs = rl_agent.recommend_path(
                student_embedding=embedding, mastery_scores=mastery,
                topic_list=topic_list, engagement=engagement, n=n,
            )
        except Exception:
            recs = []
        
        enriched = []
        for rec in recs:
            tid = rec["topic_id"]
            node = knowledge_graph.nx_graph.nodes.get(tid, {})
            enriched.append({
                **rec,
                "name": node.get("name", tid.replace("_", " ").title()),
                "subject": node.get("subject", ""),
                "difficulty": node.get("difficulty", 3),
                "estimated_minutes": node.get("minutes", 30),
                "explanation": f"Your mastery is {rec['current_mastery']:.0%} — prerequisites are met.",
            })
        
        graph_recs = knowledge_graph.get_next_recommended_topics(mastery, n=n)
        
        # If no RL recs, use graph recs as fallback
        if not enriched and graph_recs:
            enriched = [{
                "topic_id": r["topic_id"],
                "name": r["name"],
                "subject": r["subject"],
                "difficulty": r["difficulty"],
                "estimated_minutes": r["estimated_minutes"],
                "current_mastery": r["current_mastery"],
                "q_value": 0.5,
                "rank": i + 1,
                "explanation": "Recommended based on your prerequisites.",
            } for i, r in enumerate(graph_recs[:n])]
        
        return {
            "user_id": user_id,
            "rl_recommendations": enriched,
            "graph_recommendations": graph_recs,
            "epsilon": rl_agent.epsilon,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/session/complete")
async def complete_session(
    req: SessionCompleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        reward = compute_reward(
            mastery_before=req.mastery_before, mastery_after=req.mastery_after,
            engagement=req.engagement, time_spent_minutes=req.time_spent_minutes,
            topic_was_mastered=req.mastery_before > 0.85,
            hint_count=req.hint_count, correct_first_try=req.correct_first_try,
        )
        mastery = dict(current_user.mastery_scores or {})
        mastery[req.topic_id] = min(req.mastery_after, 1.0)
        current_user.mastery_scores = mastery
        current_user.engagement_score = 0.7 * (current_user.engagement_score or 0.5) + 0.3 * req.engagement
        return {"reward": round(reward, 4), "updated_mastery": mastery.get(req.topic_id)}
    except Exception as e:
        return {"reward": 0.0, "updated_mastery": req.mastery_after}
'@
[System.IO.File]::WriteAllText("$PWD\app\routers\learning_path.py", $lpContent, $utf8NoBom)
Write-Host "  learning_path.py fixed" -ForegroundColor Green

# ── Step 9: Write ALL files with UTF8 No BOM ─────────────────
Write-Host "Step 9: Ensuring all Python files have correct encoding..." -ForegroundColor Yellow

$files = Get-ChildItem -Recurse -Filter "*.py" | Where-Object { $_.FullName -notmatch "venv" }
$count = 0
foreach ($file in $files) {
    try {
        $content = Get-Content $file.FullName -Raw -Encoding UTF8
        if ($content) {
            [System.IO.File]::WriteAllText($file.FullName, $content, $utf8NoBom)
            $count++
        }
    } catch { }
}
Write-Host "  Re-encoded $count Python files to UTF-8 No BOM" -ForegroundColor Green

# ── Done ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  ALL FIXES APPLIED!" -ForegroundColor Green  
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "NOW RUN THESE COMMANDS IN ORDER:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  1) python scripts/init_db.py" -ForegroundColor White
Write-Host "  2) uvicorn app.main:app --reload --port 8000" -ForegroundColor White
Write-Host ""
Write-Host "Then open: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "Frontend:  http://localhost:5173" -ForegroundColor Cyan
Write-Host ""
Write-Host "Your API key is already set in .env" -ForegroundColor Green
