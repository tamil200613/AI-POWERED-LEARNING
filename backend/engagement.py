"""
Engagement Router — Real-time behavioral analytics
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
import time

router = APIRouter()

_engagement_buffer: dict = {}


class EngagementEvent(BaseModel):
    user_id: str
    event_type: str
    topic_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None


def _compute_score(events: list) -> float:
    if not events:
        return 0.5
    recent = [e for e in events if time.time() - e["ts"] < 300]
    if not recent:
        return 0.3
    interaction_rate = min(len(recent) / 50, 1.0)
    positive = sum(1 for e in recent if e["type"] in ("click", "scroll", "video_play"))
    negative = sum(1 for e in recent if e["type"] in ("blur", "pause"))
    ratio = positive / max(positive + negative, 1)
    return float(0.5 * interaction_rate + 0.5 * ratio)


@router.post("/event")
async def log_engagement_event(event: EngagementEvent):
    uid = event.user_id
    if uid not in _engagement_buffer:
        _engagement_buffer[uid] = []
    _engagement_buffer[uid].append({
        "type": event.event_type,
        "topic": event.topic_id,
        "ts": event.timestamp or time.time(),
        "meta": event.metadata,
    })
    _engagement_buffer[uid] = _engagement_buffer[uid][-1000:]
    score = _compute_score(_engagement_buffer[uid])
    return {"received": True, "engagement_score": round(score, 3)}


@router.get("/{user_id}/score")
async def get_engagement_score(user_id: str):
    events = _engagement_buffer.get(user_id, [])
    return {
        "user_id": user_id,
        "engagement_score": round(_compute_score(events), 3),
        "event_count": len(events),
    }


@router.get("/{user_id}/attention")
async def get_attention_stats(user_id: str):
    events = _engagement_buffer.get(user_id, [])
    recent = [e for e in events if time.time() - e["ts"] < 300]
    blur = sum(1 for e in recent if e["type"] == "blur")
    pause = sum(1 for e in recent if e["type"] == "pause")
    scroll = sum(1 for e in recent if e["type"] == "scroll")
    click = sum(1 for e in recent if e["type"] == "click")

    level = "high"
    if blur > 5 or pause > 3:
        level = "low"
    elif blur > 2 or pause > 1:
        level = "medium"

    return {
        "attention_level": level,
        "blur_events": blur,
        "interactions_per_minute": (scroll + click) / 5.0,
        "distraction_score": round(min(blur / 10, 1.0), 2),
        "recommendation": (
            "You seem distracted. Try a 5-minute break!" if level == "low"
            else "Great focus! Keep it up." if level == "high"
            else "Moderate focus — minimize distractions."
        ),
    }
