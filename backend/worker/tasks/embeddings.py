"""Celery tasks for embedding generation."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.ingestion.embeddings import generate_embeddings_batch
from worker.celery_app import celery_app

_engine = create_async_engine(settings.database_url)
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _run_embedding_generation():
    async with _session_factory() as db:
        count = await generate_embeddings_batch(db, batch_size=100)
    return count


@celery_app.task(name="worker.tasks.embeddings.generate_embeddings")
def generate_embeddings():
    """Generate embeddings for events that don't have them."""
    count = asyncio.run(_run_embedding_generation())
    return f"Generated embeddings for {count} events"
