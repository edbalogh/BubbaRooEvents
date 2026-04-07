"""local sources data model: rename events, add venues, canonical_events, extend event_sources

Revision ID: 001_local_sources
Revises: 4bc359cce68b
Create Date: 2026-04-07

"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "001_local_sources"
down_revision: Union[str, None] = "4bc359cce68b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create venues table (needed before raw_events FK)
    op.create_table(
        "venues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("slug", sa.String(350), nullable=False, unique=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(50), nullable=True),
        sa.Column("lat", sa.Float, nullable=True),
        sa.Column("lon", sa.Float, nullable=True),
        sa.Column("website_url", sa.Text, nullable=True),
        sa.Column("source_slugs", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_venues_city", "venues", ["city"])

    # 2. Create canonical_events table (needed before raw_events FK)
    op.create_table(
        "canonical_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("venues.id"), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("price_min", sa.Numeric(10, 2), nullable=True),
        sa.Column("price_max", sa.Numeric(10, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("image_url", sa.Text, nullable=True),
        sa.Column("categories", postgresql.JSONB, nullable=True),
        sa.Column("field_sources", postgresql.JSONB, nullable=True),
        sa.Column("conflicts", postgresql.JSONB, nullable=True),
        sa.Column("is_duplicate_of", postgresql.UUID(as_uuid=True), sa.ForeignKey("canonical_events.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_canonical_events_starts_at", "canonical_events", ["starts_at"])
    op.create_index("ix_canonical_events_status", "canonical_events", ["status"])

    # 3. Rename events → raw_events
    op.rename_table("events", "raw_events")

    # Rename associated indexes
    op.execute("ALTER INDEX ix_events_city RENAME TO ix_raw_events_city")
    op.execute("ALTER INDEX ix_events_starts_at RENAME TO ix_raw_events_starts_at")
    op.execute("ALTER INDEX ix_events_status RENAME TO ix_raw_events_status")

    # 4. Add new columns to raw_events
    op.add_column("raw_events", sa.Column(
        "venue_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("venues.id"), nullable=True
    ))
    op.add_column("raw_events", sa.Column(
        "canonical_event_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("canonical_events.id"), nullable=True
    ))
    op.create_index("ix_raw_events_canonical_event_id", "raw_events", ["canonical_event_id"])

    # 5. event_categories FK needs no update — event_id is UUID on raw_events, constraint still valid

    # 6. Extend event_sources with new columns
    op.add_column("event_sources", sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("event_sources", sa.Column("last_discovery_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("event_sources", sa.Column("scrape_status", sa.String(20), server_default="active", nullable=False))
    op.add_column("event_sources", sa.Column("scrape_config", postgresql.JSONB, nullable=True))
    op.add_column("event_sources", sa.Column("discovery_confidence", sa.Float, nullable=True))
    op.add_column("event_sources", sa.Column("discovered_by", sa.String(20), server_default="manual", nullable=False))

    # 7. Backfill: create one canonical_event per existing raw_event
    op.execute("""
        INSERT INTO canonical_events (
            id, title, description, starts_at, ends_at,
            price_min, price_max, currency, url, image_url,
            status, created_at, updated_at
        )
        SELECT
            gen_random_uuid(), title, description, starts_at, ends_at,
            price_min, price_max, currency, url, image_url,
            status, created_at, updated_at
        FROM raw_events
    """)

    # Use IS NOT DISTINCT FROM for nullable url column (NULL = NULL is always false in SQL).
    # Subquery with LIMIT 1 ensures deterministic 1:1 mapping when duplicate (title, starts_at, url)
    # tuples exist across sources.
    op.execute("""
        UPDATE raw_events re
        SET canonical_event_id = (
            SELECT ce.id
            FROM canonical_events ce
            WHERE ce.title = re.title
              AND ce.starts_at = re.starts_at
              AND ce.url IS NOT DISTINCT FROM re.url
            LIMIT 1
        )
    """)


def downgrade() -> None:
    # 1. Remove event_sources additions
    op.drop_column("event_sources", "discovered_by")
    op.drop_column("event_sources", "discovery_confidence")
    op.drop_column("event_sources", "scrape_config")
    op.drop_column("event_sources", "scrape_status")
    op.drop_column("event_sources", "last_discovery_at")
    op.drop_column("event_sources", "last_scraped_at")

    # 2. Remove raw_events FK columns (also drops FK constraints)
    op.drop_index("ix_raw_events_canonical_event_id", "raw_events")
    op.drop_column("raw_events", "canonical_event_id")
    op.drop_column("raw_events", "venue_id")

    # 3. Drop canonical_events and venues before renaming table (cleaner dependency order)
    op.drop_index("ix_canonical_events_status", "canonical_events")
    op.drop_index("ix_canonical_events_starts_at", "canonical_events")
    op.drop_table("canonical_events")
    op.drop_index("ix_venues_city", "venues")
    op.drop_table("venues")

    # 4. Rename indexes and table back
    op.execute("ALTER INDEX ix_raw_events_status RENAME TO ix_events_status")
    op.execute("ALTER INDEX ix_raw_events_starts_at RENAME TO ix_events_starts_at")
    op.execute("ALTER INDEX ix_raw_events_city RENAME TO ix_events_city")
    op.rename_table("raw_events", "events")
