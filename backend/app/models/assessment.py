from sqlalchemy import Column, String, Float, JSON, DateTime, Integer, Boolean, ForeignKey, Text
from sqlalchemy.sql import func
import uuid
from app.database import Base


# ─── Learning Session ─────────────────────────────────────────────

class LearningSession(Base):
    __tablename__ = "learning_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

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


# ─── Assessment ───────────────────────────────────────────────────

class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(String, ForeignKey("learning_sessions.id"), nullable=True)

    topic_id = Column(String(100), nullable=False)

    question_id = Column(String(100))
    question_text = Column(Text)
    question_type = Column(String(50))

    difficulty = Column(Float, default=0.5)

    # IRT parameters
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


# ─── Knowledge Graph Items ────────────────────────────────────────

class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

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