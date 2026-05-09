"""
AI Tutor Router
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.ai.ai_tutor import ai_tutor
from app.routers.auth import get_current_user

router = APIRouter()


class ChatMessage(BaseModel):
    role: str   # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    topic: Optional[str] = "general"
    mode: Optional[str] = "explain"   # explain / solve / quiz / example


@router.post("/chat")
async def tutor_chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    """AI tutor conversation with RAG-powered responses."""
    student_profile = {
        "learning_style": current_user.learning_style or "visual",
        "irt_ability": current_user.irt_ability or 0.0,
        "cognitive_level": current_user.cognitive_level or 0.5,
        "engagement_score": current_user.engagement_score or 0.5,
        "mastery_scores": current_user.mastery_scores or {},
    }

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    response = ai_tutor.chat(
        messages=messages,
        student_profile=student_profile,
        topic=req.topic,
        mode=req.mode,
    )

    return {"response": response, "topic": req.topic, "mode": req.mode}


@router.post("/evaluate")
async def evaluate_answer(
    student_answer: str,
    correct_answer: str,
    current_user: User = Depends(get_current_user),
):
    """Evaluate a student answer using LLM semantic grading."""
    result = ai_tutor.evaluate_answer(student_answer, correct_answer)
    return result
