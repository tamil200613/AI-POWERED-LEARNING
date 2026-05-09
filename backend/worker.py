from celery import Celery
from app.config import settings

celery_app = Celery(
    "adaptive_learning",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks"],
)

celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.timezone = "UTC"

# Periodic tasks
celery_app.conf.beat_schedule = {
    "update-student-models-hourly": {
        "task": "app.tasks.update_student_models",
        "schedule": 3600.0,
    },
    "retrain-rl-agent-daily": {
        "task": "app.tasks.retrain_rl_agent",
        "schedule": 86400.0,
    },
}
