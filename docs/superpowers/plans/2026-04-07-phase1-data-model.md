# Local Source Discovery: Phase 1 — Data Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename `events` → `raw_events`, add `venues`, `canonical_events` tables, and extend `event_sources` with discovery/scraping fields.

**Architecture:** Alembic migration renames the existing `events` table and adds three new tables. SQLAlchemy ORM models are updated to match. All existing code referencing the `Event` model is updated to use `RawEvent`. A backfill step creates one `CanonicalEvent` per existing `RawEvent` so the system continues to work immediately after migration.

**Tech Stack:** SQLAlchemy 2.x (async), Alembic, PostgreSQL, pytest-asyncio

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Modify | `backend/app/models/event.py` | Rename `Event` → `RawEvent`, add `canonical_event_id` + `venue_id` FK |
| Create | `backend/app/models/venue.py` | `Venue` ORM model |
| Create | `backend/app/models/canonical_event.py` | `CanonicalEvent` ORM model |
| Modify | `backend/app/models/source.py` | Add scraping/discovery fields to `EventSource` |
| Create | `backend/alembic/versions/001_local_sources_data_model.py` | Migration: rename table, add tables, add columns |
| Modify | `backend/app/ingestion/ingest_service.py` | `upsert_events` writes to `raw_events` |
| Modify | `backend/app/services/event_service.py` | Queries use `RawEvent` (canonical layer comes in Phase 3) |
| Modify | `backend/app/api/v1/events.py` | Import `RawEvent` instead of `Event` |
| Modify | `backend/app/services/recommendation_service.py` | Import `RawEvent` instead of `Event` |
| Create | `backend/tests/models/test_raw_event.py` | Tests for `RawEvent` model constraints |
| Create | `backend/tests/models/test_venue.py` | Tests for `Venue` model |
| Create | `backend/tests/models/test_canonical_event.py` | Tests for `CanonicalEvent` model |

---

### Task 1: Rename `Event` → `RawEvent` in ORM model

**Files:**
- Modify: `backend/app/models/event.py`

- [ ] **Step 1: Read the current file**

Open `backend/app/models/event.py`. Note the class is named `Event` with `__tablename__ = "events"`.

- [ ] **Step 2: Update the model**

Replace the entire contents of `backend/app/models/event.py` with:

```python
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RawEvent(Base):
    __tablename__ = "raw_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    venue_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("venues.id"), nullable=True)
    venue_name: Mapped[str | None] = mapped_column(String(300))
    venue_address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(100), index=True)
    state: Mapped[str | None] = mapped_column(String(50))
    country: Mapped[str] = mapped_column(String(10), default="US")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    on_sale_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    price_min: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    price_max: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    url: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    raw_data: Mapped[dict | None] = mapped_column(JSONB)
    canonical_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_events.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("uq_source_external_id", "source", "external_id", unique=True),
    )


class EventCategory(Base):
    __tablename__ = "event_categories"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    category_id: Mapped[int] = mapped_column(Integer, primary_key=True)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/event.py
git commit -m "refactor: rename Event→RawEvent, add venue_id and canonical_event_id FKs"
```

---

### Task 2: Create `Venue` ORM model

**Files:**
- Create: `backend/app/models/venue.py`
- Create: `backend/tests/models/__init__.py`
- Create: `backend/tests/models/test_venue.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/models/__init__.py` (empty).

Create `backend/tests/models/test_venue.py`:

```python
import uuid
import pytest
from app.models.venue import Venue


def test_venue_has_required_fields():
    v = Venue(
        id=uuid.uuid4(),
        name="3rd & Lindsley",
        slug="3rd-and-lindsley-nashville",
        city="Nashville",
        state="TN",
    )
    assert v.name == "3rd & Lindsley"
    assert v.slug == "3rd-and-lindsley-nashville"
    assert v.city == "Nashville"


def test_venue_optional_fields_default_none():
    v = Venue(id=uuid.uuid4(), name="Test Venue", slug="test-venue", city="Nashville", state="TN")
    assert v.address is None
    assert v.lat is None
    assert v.lon is None
    assert v.website_url is None
    assert v.source_slugs is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/models/test_venue.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.models.venue'`

- [ ] **Step 3: Create the Venue model**

Create `backend/app/models/venue.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(String(350), unique=True, nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    state: Mapped[str | None] = mapped_column(String(50))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    website_url: Mapped[str | None] = mapped_column(Text)
    source_slugs: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/models/test_venue.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/venue.py backend/tests/models/
git commit -m "feat: add Venue ORM model"
```

---

### Task 3: Create `CanonicalEvent` ORM model

**Files:**
- Create: `backend/app/models/canonical_event.py`
- Create: `backend/tests/models/test_canonical_event.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/models/test_canonical_event.py`:

```python
import uuid
from datetime import datetime, UTC
import pytest
from app.models.canonical_event import CanonicalEvent


def test_canonical_event_has_required_fields():
    event_id = uuid.uuid4()
    venue_id = uuid.uuid4()
    ce = CanonicalEvent(
        id=event_id,
        title="Test Concert",
        venue_id=venue_id,
        starts_at=datetime(2026, 5, 1, 20, 0, tzinfo=UTC),
        status="active",
    )
    assert ce.title == "Test Concert"
    assert ce.venue_id == venue_id
    assert ce.status == "active"


def test_canonical_event_optional_fields_default_none():
    ce = CanonicalEvent(
        id=uuid.uuid4(),
        title="Test",
        starts_at=datetime(2026, 5, 1, 20, 0, tzinfo=UTC),
        status="active",
    )
    assert ce.conflicts is None
    assert ce.field_sources is None
    assert ce.is_duplicate_of is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/models/test_canonical_event.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.models.canonical_event'`

- [ ] **Step 3: Create the CanonicalEvent model**

Create `backend/app/models/canonical_event.py`:

```python
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CanonicalEvent(Base):
    __tablename__ = "canonical_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    venue_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("venues.id"), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    price_min: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    price_max: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    url: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    categories: Mapped[dict | None] = mapped_column(JSONB)
    # e.g. {"price": "venue_scraper", "description": "ticketmaster"}
    field_sources: Mapped[dict | None] = mapped_column(JSONB)
    # e.g. {"price": [{"source": "ticketmaster", "value": 45}, {"source": "venue", "value": 40}]}
    conflicts: Mapped[dict | None] = mapped_column(JSONB)
    is_duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_events.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/models/test_canonical_event.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/canonical_event.py backend/tests/models/test_canonical_event.py
git commit -m "feat: add CanonicalEvent ORM model"
```

---

### Task 4: Extend `EventSource` model

**Files:**
- Modify: `backend/app/models/source.py`

- [ ] **Step 1: Add new fields to EventSource**

Replace the `EventSource` class in `backend/app/models/source.py` with:

```python
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
```

Also add the JSONB import at the top of the file — update the imports line:

```python
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/models/source.py
git commit -m "feat: add discovery and scraping fields to EventSource model"
```

---

### Task 5: Write Alembic migration

**Files:**
- Create: `backend/alembic/versions/001_local_sources_data_model.py`

- [ ] **Step 1: Create the migration file**

Create `backend/alembic/versions/001_local_sources_data_model.py`:

```python
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

    # 5. Update event_categories FK (still references raw_events via event_id UUID, no change needed)

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

    op.execute("""
        UPDATE raw_events re
        SET canonical_event_id = ce.id
        FROM canonical_events ce
        WHERE ce.title = re.title
          AND ce.starts_at = re.starts_at
          AND ce.url = re.url
    """)


def downgrade() -> None:
    op.drop_column("event_sources", "discovered_by")
    op.drop_column("event_sources", "discovery_confidence")
    op.drop_column("event_sources", "scrape_config")
    op.drop_column("event_sources", "scrape_status")
    op.drop_column("event_sources", "last_discovery_at")
    op.drop_column("event_sources", "last_scraped_at")

    op.drop_index("ix_raw_events_canonical_event_id", "raw_events")
    op.drop_column("raw_events", "canonical_event_id")
    op.drop_column("raw_events", "venue_id")

    op.execute("ALTER INDEX ix_raw_events_status RENAME TO ix_events_status")
    op.execute("ALTER INDEX ix_raw_events_starts_at RENAME TO ix_events_starts_at")
    op.execute("ALTER INDEX ix_raw_events_city RENAME TO ix_events_city")
    op.rename_table("raw_events", "events")

    op.drop_table("canonical_events")
    op.drop_index("ix_venues_city", "venues")
    op.drop_table("venues")
```

- [ ] **Step 2: Run migration**

```bash
docker exec bubbarooevents-api-1 alembic upgrade head
```

Expected output ends with: `Running upgrade 4bc359cce68b -> 001_local_sources`

- [ ] **Step 3: Verify tables exist**

```bash
docker exec bubbarooevents-db-1 psql -U bubbaroo -d bubbaroo_events -c "\dt"
```

Expected: tables `venues`, `canonical_events`, `raw_events` present; `events` absent.

- [ ] **Step 4: Verify backfill worked**

```bash
docker exec bubbarooevents-db-1 psql -U bubbaroo -d bubbaroo_events \
  -c "SELECT COUNT(*) FROM raw_events WHERE canonical_event_id IS NOT NULL;"
```

Expected: count matches total rows in `raw_events`.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/001_local_sources_data_model.py
git commit -m "feat: add migration for venues, canonical_events, rename events→raw_events"
```

---

### Task 6: Update all code referencing `Event` model

**Files:**
- Modify: `backend/app/ingestion/ingest_service.py`
- Modify: `backend/app/services/event_service.py`
- Modify: `backend/app/services/recommendation_service.py`
- Modify: `backend/app/api/v1/events.py`

- [ ] **Step 1: Update ingest_service.py**

In `backend/app/ingestion/ingest_service.py`, change the import:

```python
# Old:
from app.models.event import Event, EventCategory
# New:
from app.models.event import RawEvent, EventCategory
```

Change all references from `Event` → `RawEvent` in the `upsert_events` function body (two occurrences: `insert(Event)` and `Event.id`).

- [ ] **Step 2: Update event_service.py**

In `backend/app/services/event_service.py`, change the import:

```python
# Old:
from app.models.event import Event, EventCategory
# New:
from app.models.event import RawEvent, EventCategory
```

Change all references from `Event` → `RawEvent` in the file body.

- [ ] **Step 3: Update recommendation_service.py**

```bash
grep -n "from app.models.event import" backend/app/services/recommendation_service.py
```

Update that import line: `Event` → `RawEvent`. Update all usages in the file.

- [ ] **Step 4: Update events API**

```bash
grep -rn "from app.models.event import" backend/app/api/
```

For each file found, update `Event` → `RawEvent` in import and usage.

- [ ] **Step 5: Find any remaining references**

```bash
grep -rn "from app.models.event import Event" backend/app/
grep -rn "models.event.Event" backend/app/
```

Fix any remaining occurrences.

- [ ] **Step 6: Restart API and verify it starts cleanly**

```bash
docker compose restart api
sleep 5
docker logs bubbarooevents-api-1 --tail=20
```

Expected: no import errors, API starts with "Application startup complete."

- [ ] **Step 7: Commit**

```bash
git add backend/app/ingestion/ingest_service.py \
        backend/app/services/event_service.py \
        backend/app/services/recommendation_service.py \
        backend/app/api/v1/events.py
git commit -m "refactor: update all Event references to RawEvent after table rename"
```

---

### Task 7: Export new models from `__init__`

**Files:**
- Modify: `backend/app/models/__init__.py` (create if missing)

- [ ] **Step 1: Check if __init__.py exists**

```bash
ls backend/app/models/__init__.py 2>/dev/null || echo "missing"
```

- [ ] **Step 2: Ensure all models are importable**

Create or update `backend/app/models/__init__.py`:

```python
from app.models.canonical_event import CanonicalEvent
from app.models.category import Category
from app.models.event import EventCategory, RawEvent
from app.models.notification import Notification
from app.models.source import EventSource, UserSourcePreference
from app.models.user import User
from app.models.venue import Venue

__all__ = [
    "CanonicalEvent",
    "Category",
    "EventCategory",
    "Notification",
    "RawEvent",
    "EventSource",
    "UserSourcePreference",
    "User",
    "Venue",
]
```

- [ ] **Step 3: Run all tests**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/__init__.py
git commit -m "chore: export all models from app.models __init__"
```
