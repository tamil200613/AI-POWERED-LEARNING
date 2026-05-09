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
        result = await db.execute(select(User).where(User.id == user_id))
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
                "explanation": f"Your mastery is {rec['current_mastery']:.0%} Ã¢â‚¬â€ prerequisites are met.",
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