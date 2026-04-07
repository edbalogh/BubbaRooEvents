from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "bubbaroo",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "worker.tasks.ingestion",
        "worker.tasks.embeddings",
        "worker.tasks.notifications",
        "worker.tasks.preferences",
        "worker.tasks.scrapers",
        "worker.tasks.discovery",
        "worker.tasks.dedup",
    ],
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
        "ingest-seatgeek-events": {
            "task": "worker.tasks.ingestion.ingest_seatgeek",
            "schedule": 1800.0,  # every 30 minutes
        },
        "ingest-bandsintown-events": {
            "task": "worker.tasks.ingestion.ingest_bandsintown",
            "schedule": 3600.0,  # every hour
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
        # --- Preference Learning ---
        "recompute-preferences": {
            "task": "worker.tasks.preferences.recompute_preferences",
            "schedule": 21600.0,  # every 6 hours
        },
        # --- Venue Scrapers ---
        "scrape-venues": {
            "task": "worker.tasks.scrapers.scrape_venues",
            "schedule": 21600.0,  # every 6 hours
        },
        # --- Source Discovery & Scraping ---
        "discover-sources-weekly": {
            "task": "worker.tasks.discovery.discover_sources",
            "schedule": crontab(hour=2, minute=0, day_of_week=0),  # Sunday 2am UTC
        },
        "scrape-all-sources-daily": {
            "task": "worker.tasks.discovery.scrape_all_sources",
            "schedule": crontab(hour=3, minute=0),  # Daily 3am UTC
        },
        # --- Deduplication ---
        "dedup-events-hourly": {
            "task": "worker.tasks.dedup.dedup_events",
            "schedule": crontab(minute=30),  # :30 past every hour
        },
    },
)
