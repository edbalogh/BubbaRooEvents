from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "bubbaroo",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["worker.tasks.ingestion", "worker.tasks.embeddings", "worker.tasks.notifications"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        # --- National API sources ---
        "ingest-ticketmaster-events": {
            "task": "worker.tasks.ingestion.ingest_ticketmaster",
            "schedule": 900.0,  # every 15 minutes
        },
        "ingest-meetup-events": {
            "task": "worker.tasks.ingestion.ingest_meetup",
            "schedule": 1800.0,  # every 30 minutes
        },
        "ingest-eventbrite-events": {
            "task": "worker.tasks.ingestion.ingest_eventbrite",
            "schedule": 1800.0,  # every 30 minutes
        },
        "ingest-bandsintown-events": {
            "task": "worker.tasks.ingestion.ingest_bandsintown",
            "schedule": 3600.0,  # every hour
        },
        # --- Development ---
        "ingest-mock-events": {
            "task": "worker.tasks.ingestion.ingest_mock_events",
            "schedule": 3600.0,  # every hour (development only)
        },
        # --- Embeddings ---
        "generate-embeddings": {
            "task": "worker.tasks.embeddings.generate_embeddings",
            "schedule": 3600.0,  # every hour
        },
        # --- Notifications ---
        "send-tonight-notifications": {
            "task": "worker.tasks.notifications.send_tonight_notifications",
            "schedule": 3600.0,  # every hour (filtered to evening in service)
        },
        "send-ticket-alerts": {
            "task": "worker.tasks.notifications.send_ticket_alerts",
            "schedule": 1800.0,  # every 30 min (matches ingestion cycle)
        },
        "send-new-match-notifications": {
            "task": "worker.tasks.notifications.send_new_match_notifications",
            "schedule": 86400.0,  # once per day
        },
        "send-weekly-digest": {
            "task": "worker.tasks.notifications.send_weekly_digest",
            "schedule": 604800.0,  # once per week
        },
    },
)
