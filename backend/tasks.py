"""
Celery background tasks for async ML operations.
"""
from app.worker import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.update_student_models")
def update_student_models():
    """Hourly: recompute student embeddings and mastery scores."""
    logger.info("Running student model update task")
    # In production: iterate all users, recompute embeddings, update DB
    return {"status": "completed"}


@celery_app.task(name="app.tasks.retrain_rl_agent")
def retrain_rl_agent():
    """Daily: retrain RL agent on accumulated experience."""
    logger.info("Running RL agent retraining task")
    from app.ai.rl_agent import rl_agent
    # Run training steps on buffered experience
    losses = []
    for _ in range(100):
        loss = rl_agent.train_step()
        if loss is not None:
            losses.append(loss)
    if losses:
        rl_agent.save_model()
    return {"status": "completed", "steps": len(losses)}
