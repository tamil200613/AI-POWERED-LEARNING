"""
Learning Path Router — RL-based personalized path generation
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.models.assessment import LearningSession
from app.ai.rl_agent import rl_agent, compute_reward
from app.ai.knowledge_graph import knowledge_graph
from app.routers.auth import get_current_user
from pydantic import BaseModel

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
async def get_learning_path(
    user_id: str,
    n: int = 5,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate personalized learning path using RL agent.
    Returns top-N recommended topics with Q-values and explanations.
    """
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    topic_list = [t["id"] for t in knowledge_graph.get_all_topics()]
    mastery_scores = user.mastery_scores or {}
    embedding = user.embedding or []
    engagement = user.engagement_score or 0.5

    # RL recommendations
    rl_recs = rl_agent.recommend_path(
        student_embedding=embedding,
        mastery_scores=mastery_scores,
        topic_list=topic_list,
        engagement=engagement,
        n=n,
    )

    # Enrich with knowledge graph data
    enriched = []
    for rec in rl_recs:
        tid = rec["topic_id"]
        node = knowledge_graph.nx_graph.nodes.get(tid, {})
        prereqs = knowledge_graph.get_prerequisites(tid, depth=2)
        prereq_mastery = {p: mastery_scores.get(p, 0.0) for p in prereqs}
        enriched.append({
            **rec,
            "name": node.get("name", tid),
            "subject": node.get("subject", ""),
            "difficulty": node.get("difficulty", 3),
            "estimated_minutes": node.get("minutes", 30),
            "prerequisites": prereq_mastery,
            "explanation": f"Recommended because your mastery is {rec['current_mastery']:.0%} and prerequisites are met.",
        })

    # Also include graph-based recommendations for comparison
    graph_recs = knowledge_graph.get_next_recommended_topics(mastery_scores, n=n)

    return {
        "user_id": user_id,
        "rl_recommendations": enriched,
        "graph_recommendations": graph_recs,
        "epsilon": rl_agent.epsilon,  # exploration rate
    }


@router.post("/session/complete")
async def complete_session(
    req: SessionCompleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Called when a student finishes a learning session.
    Computes reward and triggers RL update.
    """
    reward = compute_reward(
        mastery_before=req.mastery_before,
        mastery_after=req.mastery_after,
        engagement=req.engagement,
        time_spent_minutes=req.time_spent_minutes,
        topic_was_mastered=req.mastery_before > 0.85,
        hint_count=req.hint_count,
        correct_first_try=req.correct_first_try,
    )

    # Update user mastery in DB
    user = current_user
    mastery = dict(user.mastery_scores or {})
    mastery[req.topic_id] = min(req.mastery_after, 1.0)
    user.mastery_scores = mastery
    user.engagement_score = 0.7 * (user.engagement_score or 0.5) + 0.3 * req.engagement

    # Update LearningSession record
    session_result = await db.execute(
        select(LearningSession).where(LearningSession.id == uuid.UUID(req.session_id))
    )
    session = session_result.scalar_one_or_none()
    if session:
        session.post_mastery = req.mastery_after
        session.learning_gain = req.mastery_after - req.mastery_before
        session.total_reward = reward
        session.engagement_reward = req.engagement

    return {"reward": round(reward, 4), "updated_mastery": mastery.get(req.topic_id)}


@router.get("/topics/all")
async def get_all_topics():
    """Return all topics in the knowledge graph."""
    return knowledge_graph.get_all_topics()


@router.get("/topics/{topic_id}/prerequisites")
async def get_topic_prerequisites(topic_id: str):
    prereqs = knowledge_graph.get_prerequisites(topic_id, depth=3)
    return {"topic_id": topic_id, "prerequisites": prereqs}
