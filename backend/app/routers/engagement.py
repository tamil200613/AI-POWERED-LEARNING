from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any, Optional
import time

router = APIRouter()
_buf: dict = {}

class EngagementEvent(BaseModel):
    user_id: str
    event_type: str
    topic_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None

def _score(events):
    if not events: return 0.5
    recent = [e for e in events if time.time() - e["ts"] < 300]
    if not recent: return 0.3
    pos = sum(1 for e in recent if e["type"] in ("click","scroll","video_play"))
    neg = sum(1 for e in recent if e["type"] in ("blur","pause"))
    return float(0.5 * min(len(recent)/50,1.0) + 0.5 * pos/max(pos+neg,1))

@router.post("/event")
async def log_event(event: EngagementEvent):
    uid = event.user_id
    if uid not in _buf: _buf[uid] = []
    _buf[uid].append({"type": event.event_type, "topic": event.topic_id, "ts": event.timestamp or time.time()})
    _buf[uid] = _buf[uid][-1000:]
    return {"received": True, "engagement_score": round(_score(_buf[uid]), 3)}

@router.get("/{user_id}/score")
async def get_score(user_id: str):
    return {"user_id": user_id, "engagement_score": round(_score(_buf.get(user_id,[])), 3), "event_count": len(_buf.get(user_id,[]))}

@router.get("/{user_id}/attention")
async def get_attention(user_id: str):
    events = _buf.get(user_id, [])
    recent = [e for e in events if time.time() - e["ts"] < 300]
    blur = sum(1 for e in recent if e["type"] == "blur")
    pause = sum(1 for e in recent if e["type"] == "pause")
    level = "low" if blur > 5 or pause > 3 else "medium" if blur > 2 else "high"
    return {
        "attention_level": level,
        "blur_events": blur,
        "interactions_per_minute": len([e for e in recent if e["type"] in ("click","scroll")])/5.0,
        "distraction_score": round(min(blur/10,1.0),2),
        "recommendation": "Try a 5-minute break!" if level=="low" else "Great focus!" if level=="high" else "Minimize distractions.",
    }
