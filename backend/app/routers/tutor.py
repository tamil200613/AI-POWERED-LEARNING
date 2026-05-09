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
