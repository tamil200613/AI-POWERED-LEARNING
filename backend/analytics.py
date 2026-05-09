"""
Analytics Router — Learning analytics, predictions, heatmaps
"""
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
async def get_knowledge_heatmap(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    mastery    = user.mastery_scores or {}
    all_topics = knowledge_graph.get_all_topics()
    importance = knowledge_graph.compute_topic_importance()

    subjects = {}
    for topic in all_topics:
        tid     = topic["id"]
        subject = topic.get("subject", "other")
        if subject not in subjects:
            subjects[subject] = []
        subjects[subject].append({
            "topic_id":  tid,
            "name":      topic.get("name", tid),
            "mastery":   mastery.get(tid, 0.0),
            "difficulty":topic.get("difficulty", 3),
            "importance":importance.get(tid, 0.0),
            "status": (
                "mastered" if mastery.get(tid, 0.0) >= 0.8 else
                "learning" if mastery.get(tid, 0.0) >= 0.4 else "gap"
            ),
        })

    gap_subgraph = knowledge_graph.get_knowledge_gap_subgraph(mastery, threshold=0.6)

    return {
        "user_id":      user_id,
        "subjects":     subjects,
        "gap_subgraph": gap_subgraph,
        "summary": {
            "total_topics":   len(all_topics),
            "mastered":       sum(1 for t in all_topics if mastery.get(t["id"], 0) >= 0.8),
            "learning":       sum(1 for t in all_topics if 0.4 <= mastery.get(t["id"], 0) < 0.8),
            "gap":            sum(1 for t in all_topics if mastery.get(t["id"], 0) < 0.4),
            "overall_mastery":sum(mastery.values()) / max(len(all_topics), 1),
        },
    }


@router.get("/{user_id}/predict")
async def get_performance_prediction(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sessions_result = await db.execute(
        select(LearningSession).where(LearningSession.user_id == uuid.UUID(user_id))
        .order_by(LearningSession.started_at.asc())
    )
    sessions = [
        {c.name: getattr(s, c.name) for c in s.__table__.columns}
        for s in sessions_result.scalars().all()
    ]

    user_dict  = {c.name: getattr(user, c.name) for c in user.__table__.columns}
    prediction = performance_predictor.predict(user_dict, sessions)

    user.dropout_risk          = prediction["dropout_risk"]
    user.predicted_final_score = prediction["predicted_final_score"]

    return prediction


@router.get("/{user_id}/progress")
async def get_progress_timeline(
    user_id: str,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sessions_result = await db.execute(
        select(LearningSession).where(LearningSession.user_id == uuid.UUID(user_id))
        .order_by(LearningSession.started_at.desc()).limit(limit)
    )
    sessions = sessions_result.scalars().all()

    assessments_result = await db.execute(
        select(Assessment).where(Assessment.user_id == uuid.UUID(user_id))
        .order_by(Assessment.created_at.desc()).limit(limit)
    )
    assessments = assessments_result.scalars().all()

    return {
        "sessions": [
            {
                "date":            str(s.started_at),
                "topic":           s.topic_name,
                "learning_gain":   s.learning_gain,
                "post_mastery":    s.post_mastery,
                "duration_minutes":(s.duration_seconds or 0) / 60,
                "reward":          s.total_reward,
            }
            for s in reversed(sessions)
        ],
        "ability_trajectory": [
            {
                "date":    str(a.created_at),
                "ability": a.ability_after,
                "topic":   a.topic_id,
                "correct": a.is_correct,
            }
            for a in reversed(assessments)
            if a.ability_after is not None
        ],
    }
