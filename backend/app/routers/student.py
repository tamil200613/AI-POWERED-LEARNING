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
    result = await db.execute(select(User).where(User.id == user_id))
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
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"mastery_scores": user.mastery_scores or {}, "irt_ability": user.irt_ability, "cognitive_level": user.cognitive_level}
