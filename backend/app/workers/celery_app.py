from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery("marketplace", broker=settings.redis_url, backend=settings.redis_url, include=["app.workers.tasks"])
celery_app.conf.update(
    task_always_eager=settings.celery_eager,
    task_eager_propagates=False,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
    beat_schedule={
        "release-expired-orders": {"task": "app.workers.tasks.release_expired_orders", "schedule": crontab(minute="*/5")},
    },
)
