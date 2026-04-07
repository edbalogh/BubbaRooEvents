# Local Source Discovery, LLM-Assisted Scraping & Event Deduplication

**Date:** 2026-04-07
**Status:** Approved

## Overview

BubbaRooEvents currently ingests events only from Ticketmaster (all other API-based adapters — SeatGeek, Meetup, Eventbrite, Bandsintown — have been disabled due to defunct public APIs). This design adds:

1. **Automated local source discovery** — LLM agent searches the web weekly for city-specific event sites
2. **LLM-assisted scraping** — Crawl4AI fetches pages, Gemma 4 extracts events from unstructured content
3. **Canonical event layer** — raw source records feed a merged, deduplicated event model
4. **Venue registry** — canonical venue table with fuzzy dedup
5. **UI** — sources page, manual refresh, conflict indicators, duplicate management

All LLM work uses Gemma 4 via local Ollama. No new API keys required. Web search uses `duckduckgo-search` (no key). Scraping uses Crawl4AI (open source, local).

---

## Data Model

### `venues` (new table)

Canonical venue registry. Populated by dedup logic when raw events reference venues.

| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | str | Canonical display name |
| slug | str UNIQUE | e.g. `3rd-and-lindsley-nashville` |
| address | str | |
| city | str | |
| state | str | |
| lat | float | |
| lon | float | |
| website_url | str | |
| source_slugs | JSONB | Which sources have mentioned this venue |
| created_at | datetime | |
| updated_at | datetime | |

Dedup key: fuzzy match on `(name, city)` with >85% similarity threshold.

### `raw_events` (rename/repurpose current `events` table)

Every scrape result lands here. Nothing is deleted. The `canonical_event_id` is null until dedup runs.

| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| external_id | str | Source-assigned ID |
| source | str FK → event_sources.slug | |
| title | str | |
| description | str | |
| venue_id | UUID FK → venues | Nullable until venue resolved |
| starts_at | datetime | |
| ends_at | datetime | |
| price_min | decimal | |
| price_max | decimal | |
| currency | str | |
| url | str | |
| image_url | str | |
| categories | JSONB | |
| raw_data | JSONB | Full original payload |
| canonical_event_id | UUID FK → canonical_events | Nullable |
| created_at | datetime | |
| updated_at | datetime | |

Unique constraint: `(source, external_id)`.

### `canonical_events` (new table)

User-facing, merged event record built from one or more raw_events.

| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| title | str | Best value from sources |
| description | str | Best value from sources |
| venue_id | UUID FK → venues | |
| starts_at | datetime | |
| ends_at | datetime | |
| price_min | decimal | Best value |
| price_max | decimal | Best value |
| currency | str | |
| url | str | |
| image_url | str | |
| categories | JSONB | |
| field_sources | JSONB | `{"price": "venue_scraper", "description": "ticketmaster"}` |
| conflicts | JSONB | `{"price": [{"source": "ticketmaster", "value": 45}, {"source": "venue_scraper", "value": 40}]}` |
| is_duplicate_of | UUID FK → canonical_events | Nullable — for user-flagged merges |
| status | enum | active / merged / hidden |
| created_at | datetime | |
| updated_at | datetime | |

### `event_sources` (extend existing)

Add fields to existing `EventSource` model:

| New Field | Type | Notes |
|---|---|---|
| last_scraped_at | datetime | Updated after each scrape run |
| last_discovery_at | datetime | When this source was found by discovery |
| scrape_status | enum | active / paused / error |
| scrape_config | JSONB | CSS hints, known URL patterns for this site |
| discovery_confidence | float | LLM confidence score (0.0–1.0) that this is a real event source |
| discovered_by | enum | manual / llm_discovery |

---

## Pipeline Architecture

### Task 1: Source Discovery (weekly Celery Beat)

Celery task: `worker.tasks.discovery.discover_sources`

```
for each active city:
    1. DuckDuckGo search: "[city] events calendar", "[city] events this weekend",
       "[city] local events site"
    2. Collect top 20 URLs + snippets per query
    3. Deduplicate URLs, filter out already-known sources
    4. Gemma 4 (Tool 1 — Source Scoring): score each URL 0.0–1.0
    5. Keep candidates with score > 0.7
    6. Crawl4AI: fetch each candidate page → clean markdown
    7. Gemma 4 (Tool 2 — Source Confirmation): confirm it lists local events
    8. Confirmed sources → insert into event_sources (scrape_status=active)
    9. Queue scrape task immediately for new sources
    10. Set new_source_notification flag for all users in that city
```

Schedule: weekly (Sunday 2am).
Can be triggered on-demand via `POST /api/v1/discovery/run`.

### Task 2: Event Scraping (daily per source)

Celery task: `worker.tasks.discovery.scrape_source`

```
for each active source in event_sources:
    1. Crawl4AI: fetch source URL → clean markdown + raw HTML
    2. Fast path: if JSON-LD present → use existing generic_jsonld.py parser
    3. Slow path: Gemma 4 (Tool 3 — Event Extraction) → JSON array of events
    4. Normalize each extracted event → NormalizedEvent
    5. Upsert into raw_events
    6. Update event_sources.last_scraped_at
    7. Enqueue dedup task for new/updated raw_events
```

Schedule: daily (3am).
Can be triggered per-source via `POST /api/v1/sources/{slug}/refresh`.
Returns `job_id` for frontend polling.

### Task 3: Deduplication (triggered after each scrape batch)

Celery task: `worker.tasks.discovery.dedup_events`

```
for each raw_event without a canonical_event_id:
    1. Resolve venue:
       - Exact match on (name, city) in venues table
       - Fuzzy match >85% → use existing venue
       - No match → create new venue record
    2. Find duplicate candidates:
       - Same city + starts_at within 4-hour window
       - Same venue_id OR fuzzy venue name match >85%
    3. If strong match (same venue_id + title similarity >80%):
       - Skip LLM, treat as duplicate
    4. If weak match (fuzzy venue + same city + date window):
       - Gemma 4 (Tool 4 — Duplicate Detection): are these the same event?
       - Threshold: is_duplicate=true AND confidence > 0.8
    5. If duplicate found:
       - Find or create canonical_event
       - Link all matching raw_events to it
       - Merge fields (priority: venue_scraper > ticketmaster > others)
       - Store conflicts in canonical_events.conflicts JSONB
    6. If no duplicate:
       - Create new canonical_event from this raw_event alone
```

### Field Merge Priority

When multiple sources provide the same field, pick the best value:

| Field | Priority order |
|---|---|
| price | venue website > ticketmaster > any |
| description | longest non-null value wins |
| image | highest resolution (by URL pattern heuristic) |
| starts_at | venue website > ticketmaster > scraper |
| url | venue website > ticketmaster > any |

Losing values go into `conflicts` JSONB if they differ from winner.

---

## LLM Agent Tools

All tools use Gemma 4 via Ollama at `ollama_base_url`. JSON parse failures retry once with stricter prompt. Timeout: 60s for extraction, 30s for scoring/dedup.

### Tool 1: Source Scoring

**Input:** List of `{url, snippet}` from search results, city name
**System prompt:** `"You are evaluating URLs to find local event calendars for [city]. Score each URL 0.0-1.0 on how likely it is to be a city-specific event calendar. Penalize: national ticket resellers (Ticketmaster, StubHub), social media, news sites. Reward: city/neighborhood event listings, local venue calendars, arts council sites, parks & rec calendars."`
**User prompt:** `"Score these URLs for [city]. Return ONLY a JSON array: [{\"url\": \"...\", \"score\": 0.0, \"reason\": \"...\"}]"`
**Filter:** score > 0.7

### Tool 2: Source Confirmation

**Input:** Clean markdown of candidate page
**User prompt:** `"Does this page list local events with dates and times? Return ONLY JSON: {\"is_event_site\": bool, \"site_name\": \"str\", \"event_count_estimate\": int, \"city\": \"str\"}"`
**Filter:** `is_event_site=true`

### Tool 3: Event Extraction

**Input:** Clean markdown of event listing page
**User prompt:** `"Extract all events from this page. Return ONLY a JSON array: [{\"title\": \"str\", \"date\": \"YYYY-MM-DD\", \"time\": \"HH:MM\", \"venue\": \"str\", \"address\": \"str\", \"price\": \"str\", \"url\": \"str\", \"description\": \"str\"}]. Use null for missing fields. Only include events with at least a title and date."`
**Post-process:** Parse dates/times into datetime, normalize price strings to decimal range.

### Tool 4: Duplicate Detection

**Input:** Two event dicts `{title, venue_name, starts_at, city}`
**User prompt:** `"Are these two listings the same real-world event? Venue names may differ slightly. Return ONLY JSON: {\"is_duplicate\": bool, \"confidence\": 0.0, \"reason\": \"str\"}"`
**Threshold:** `is_duplicate=true AND confidence >= 0.8`

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/sources` | List all sources with status, last_scraped_at, event count |
| POST | `/api/v1/sources/{slug}/refresh` | Trigger immediate scrape, returns job_id |
| GET | `/api/v1/sources/{slug}/refresh/{job_id}` | Poll scrape job status |
| PATCH | `/api/v1/sources/{slug}/preference` | Per-user pause/resume (maps to existing UserSourcePreference disabled state) |
| POST | `/api/v1/sources/suggest` | User submits a URL for discovery pipeline |
| POST | `/api/v1/discovery/run` | Trigger source discovery now (admin) |
| GET | `/api/v1/discovery/status` | Last discovery run timestamp + sources found |
| GET | `/api/v1/duplicates` | List unresolved user-flagged duplicates |
| POST | `/api/v1/duplicates` | User flags two canonical_event IDs as duplicates |
| POST | `/api/v1/duplicates/{id}/merge` | Merge two canonical events |
| GET | `/api/v1/events` | Updated to return canonical_events (not raw_events) |

---

## UI

### Sources Page (`/sources`)

- Table: name, city, type (api/scraper/discovered), last scraped, event count, status badge
- Per-row: **Refresh** button (spinner while running, updates timestamp on complete), **Pause/Resume** toggle (per-user — maps to existing `UserSourcePreference` disabled state, hides events from that source for this user only)
- Top of page: last discovery run timestamp + **"Run Discovery Now"** button
- **"Suggest a Source"** button → modal, user pastes URL

### Event Card — Conflict Indicator

- Fields with conflicts show a `?` icon
- Hover tooltip: `"Ticketmaster: $45 · Venue site: $40"`
- No user action required — informational only

### Duplicate Management (`/duplicates`)

- List of user-flagged duplicate pairs, side-by-side comparison
- **Merge** button per pair — one event becomes canonical, other's raw data feeds into it
- **"Report Duplicate"** button on every event card → search modal to find the matching event

### Login Notification

- On login, if user's city has new sources discovered since last login: banner notification
- "3 new local event sources found for Nashville" with link to Sources page
- Dismissable, stored as `seen` in user session

---

## New Dependencies

```toml
# backend/pyproject.toml additions
crawl4ai = ">=0.4"
duckduckgo-search = ">=6.0"
thefuzz = ">=0.22"        # fuzzy string matching for venue dedup
python-levenshtein = ">=0.25"  # speeds up thefuzz
```

---

## Migration Notes

- Existing `events` table becomes `raw_events` — migration renames table, adds `canonical_event_id` column
- All existing Ticketmaster events get backfilled: each gets a canonical_event record (1:1 initially)
- `event_sources` table gets new columns added (all nullable, no data loss)
- All existing API/service code referencing `events` table updated to use `raw_events` → `canonical_events` query path
- Frontend event queries switch from `raw_events` to `canonical_events`

---

## Out of Scope

- Notification delivery for new sources (uses existing notification infrastructure)
- Changes to recommendation engine scoring (operates on canonical_events same as current events)
- Mobile push notifications for duplicates
