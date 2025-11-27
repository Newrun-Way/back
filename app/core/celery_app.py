# app/core/celery_app.py
from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "owpml_rag",
    broker="redis://redis:6379/0",        # docker-compose 기준
    backend="redis://redis:6379/1",
    include=[
        "app.tasks.rag_tasks"   # ★ task 자동 로드
    ]
)

celery_app.conf.update(
    task_routes={
        "app.tasks.rag_tasks.*": {"queue": "rag"},
    },
    timezone="Asia/Seoul",
    enable_utc=True,
)
