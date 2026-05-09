from sqlalchemy import Column, String, Float, JSON, DateTime, Integer, Boolean
from sqlalchemy.sql import func
import uuid
from app.database import Base


class User(Base):
    __tablename__ = "users"

    # ✅ FIXED: UUID → String
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200))

    grade_level = Column(Integer, default=10)
    learning_style = Column(String(50), default="visual")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    is_active = Column(Boolean, default=True)

    # Learning profile
    embedding = Column(JSON, default=list)
    mastery_scores = Column(JSON, default=dict)
    cognitive_level = Column(Float, default=0.5)
    engagement_score = Column(Float, default=0.7)
    learning_speed = Column(Float, default=1.0)

    # IRT metrics
    irt_ability = Column(Float, default=0.0)
    irt_ability_std = Column(Float, default=1.0)

    # Engagement metrics
    total_sessions = Column(Integer, default=0)
    avg_session_minutes = Column(Float, default=0.0)
    total_questions_answered = Column(Integer, default=0)
    overall_accuracy = Column(Float, default=0.0)
    streak_days = Column(Integer, default=0)
    last_active = Column(DateTime(timezone=True))

    # Predictions
    dropout_risk = Column(Float, default=0.0)
    predicted_final_score = Column(Float, default=0.5)