"""Event source registry and user source preferences."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EventSource(Base):
    """Registry of all event data sources (APIs, scrapers, etc.)."""

    __tablename__ = "event_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # api, scraper, manual, discovered
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_local: Mapped[bool] = mapped_column(Boolean, default=False)
    coverage_cities: Mapped[str | None] = mapped_column(Text)
    default_trust_score: Mapped[float] = mapped_column(Float, default=1.0)
    # Discovery & scraping fields
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_discovery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scrape_status: Mapped[str] = mapped_column(String(20), default="active")  # active, paused, error
    scrape_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    discovery_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    discovered_by: Mapped[str] = mapped_column(String(20), default="manual")  # manual, llm_discovery
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserSourcePreference(Base):
    """User preferences for event sources: like, dislike, or turn off."""

    __tablename__ = "user_source_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("event_sources.id"), nullable=False)
    preference: Mapped[str] = mapped_column(String(20), nullable=False)  # liked, disliked, disabled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
