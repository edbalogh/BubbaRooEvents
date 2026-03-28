from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "bubbaroo",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["worker.tasks.ingestion", "worker.tasks.embeddings"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "ingest-ticketmaster-events": {
            "task": "worker.tasks.ingestion.ingest_ticketmaster",
            "schedule": 900.0,  # every 15 minutes
        },
        "ingest-mock-events": {
            "task": "worker.tasks.ingestion.ingest_mock_events",
            "schedule": 3600.0,  # every hour (development only)
        },
        "generate-embeddings": {
            "task": "worker.tasks.embeddings.generate_embeddings",
            "schedule": 3600.0,  # every hour
        },
    },
)
