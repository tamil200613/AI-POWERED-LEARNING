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
        
        mastery_dict = dict(current_user.mastery_scores or {})
        mastery_dict[req.topic_id] = adaptive_engine.compute_mastery_score(theta_after)
        current_user.mastery_scores = mastery_dict
        
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
        q = select(Assessment).where(Assessment.user_id == user_id)
        if topic_id:
            q = q.where(Assessment.topic_id == topic_id)
        result = await db.execute(q.order_by(Assessment.created_at.desc()).limit(limit))
        return [{"id": str(a.id), "topic_id": a.topic_id, "is_correct": a.is_correct, "score": a.score, "ability_after": a.ability_after, "created_at": str(a.created_at)} for a in result.scalars().all()]
    except Exception as e:
        return []