"""
Student Profile Router
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.database import get_db
from app.models.user import User
from app.models.assessment import LearningSession, Assessment
from app.ai.student_profiler import profiler
from app.ai.knowledge_graph import knowledge_graph
from app.routers.auth import get_current_user

router = APIRouter()


@router.get("/{user_id}/profile")
async def get_student_profile(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Load session and assessment history
    sessions_result = await db.execute(
        select(LearningSession).where(LearningSession.user_id == uuid.UUID(user_id))
        .order_by(LearningSession.started_at.desc()).limit(50)
    )
    sessions = [
        {c.name: getattr(s, c.name) for c in s.__table__.columns}
        for s in sessions_result.scalars().all()
    ]

    assessments_result = await db.execute(
        select(Assessment).where(Assessment.user_id == uuid.UUID(user_id))
        .order_by(Assessment.created_at.desc()).limit(200)
    )
    assessments = [
        {c.name: getattr(a, c.name) for c in a.__table__.columns}
        for a in assessments_result.scalars().all()
    ]

    topic_ids = [t["id"] for t in knowledge_graph.get_all_topics()]
    user_dict = {c.name: getattr(user, c.name) for c in user.__table__.columns}

    profile = profiler.build_full_profile(user_dict, sessions, assessments, topic_ids)
    return profile


@router.get("/{user_id}/mastery")
async def get_mastery_scores(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "mastery_scores": user.mastery_scores or {},
        "irt_ability": user.irt_ability,
        "cognitive_level": user.cognitive_level,
    }
