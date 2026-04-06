# Home City Detection & Hierarchical Preferences Design

**Date:** 2026-04-06
**Status:** Approved

---

## Overview

Two UX improvements:

1. **Home page city detection** — Default to the user's home city, trigger live ingestion if no events exist, show a full-page loading state while events are discovered.
2. **Hierarchical preferences** — Replace the flat slider-per-category settings page with a stepped wizard: pick event types → rate base genres → optional sub-genre and artist deep-dive (with MusicBrainz artist verification).

These changes also remove all mock data infrastructure — the app moves to live data only.

---

## Part 1: Remove Mock Data

### What gets removed

- `backend/app/ingestion/mock_data.py` — delete entirely
- `backend/app/api/v1/seed.py` — delete entirely
- Route registration for `/api/v1/seed` in `backend/app/main.py`
- `ingest_mock_events` task from `backend/worker/celery_app.py` beat schedule
- `ingest_mock_events` task from `backend/worker/tasks/ingestion.py`

### What replaces it

Nothing — live ingestion via Ticketmaster and the other adapters is the only data source going forward.

---

## Part 2: Dynamic City Ingestion

### Problem

The Celery worker ingests a hardcoded list of 5 cities (`INGEST_CITIES` in `worker/tasks/ingestion.py`). Any user whose home city isn't in that list will see no events. There's also no way to trigger ingestion on demand.

### Solution

**2a. Make ingested cities dynamic**

Add a `cities` table (or derive from `User.home_city` values) that the scheduled worker queries at runtime instead of using a hardcoded dict. On each beat tick, the worker fetches `SELECT DISTINCT home_city FROM users WHERE home_city IS NOT NULL`, merges with a small set of always-on cities (e.g. Austin, Nashville), and ingests all of them.

**2b. New on-demand ingest endpoint**

```
POST /api/v1/ingest/city
Body: { "city": "Nashville" }
Auth: required (any authenticated user)
```

- Dispatches a Celery task: `ingest_city_now(city)` — runs all adapters for that city asynchronously
- Returns immediately: `{ "status": "queued", "city": "Nashville" }`
- Rate-limited per city: won't re-queue if an ingest for that city was dispatched in the last 10 minutes (checked via Redis key `ingest:city:{city}:last_queued`)

**2c. `ingest_city_now` Celery task**

New task in `worker/tasks/ingestion.py`:

```python
@celery_app.task
async def ingest_city_now(city: str):
    """On-demand ingestion for a single city across all adapters."""
    # Runs: Ticketmaster, SeatGeek, Bandsintown, Eventbrite, Meetup
    # Same logic as the scheduled tasks but parameterized to one city
```

**2d. User registration triggers ingestion**

When a user registers or updates their `home_city` in Settings, the backend:
1. Saves the city to `users.home_city`
2. Dispatches `ingest_city_now.delay(city)` if it hasn't been run recently (same Redis check)

This means within minutes of a user setting their city, live events will start appearing — even before the next scheduled beat tick.

---

## Part 3: Home Page — City Detection & Loading State

### City resolution

`Home.tsx` reads `user.home_city` from `AuthContext`. City priority:

1. User's `home_city` (if logged in and set)
2. City from URL search params (manual search)
3. `"Austin"` fallback (logged-out users only)

### First-visit detection flow

On mount, after resolving the city:

1. Call `GET /api/v1/events?city={city}&per_page=1`
2. If `total === 0`:
   - Show **full-page loading state** (see below)
   - Call `POST /api/v1/ingest/city` with `{ city }`
   - Start polling `GET /api/v1/events?city={city}&per_page=5` every 3 seconds
   - When `total > 0`, transition to normal home view (load full event list)
3. If `total > 0`: render normally

### Full-page loading state UI

```
[City emoji or icon]
Setting up [City] for you

Finding the best events in your city...

[Progress bar — width driven by event count, caps at 100% once any events arrive]
[N] events found

[Scrolling list of event titles as they appear]
  ✓ Ryman Auditorium — Bluegrass Night
  ✓ Marathon Music Works — Indie Showcase
  ⏳ Checking more sources…

[subtle "This usually takes under a minute" subtext]
```

- Progress bar goes from 0% → 100% once `total >= 10`, so it fills quickly and doesn't hang
- Event title list shows up to 5 latest found, scrolls as new ones appear
- No manual "refresh" button — auto-transitions
- If polling times out after 90 seconds with still 0 events (Ticketmaster key invalid, etc.), show a graceful error: "Couldn't find events for [City] right now. Try searching another city."

### Changes to `Home.tsx`

- Import `useAuth` to read `user.home_city`
- Replace hardcoded `{ city: 'Austin' }` initial state with resolved city
- Add `CityLoadingScreen` component (new file: `frontend/src/components/CityLoadingScreen.tsx`)
- Add `useCitySeeding` hook (new file: `frontend/src/hooks/useCitySeeding.ts`) encapsulating: check → trigger → poll → resolve logic

---

## Part 4: Settings — Preferences Tab with Stepped Wizard

### Tab restructure

The Settings page gets a tab bar at the top:

| Tab | Contents |
|-----|----------|
| **General** | Distance preference, home city (editable), timezone |
| **Preferences** | Stepped wizard (new — see below) |
| **Notifications** | Channels + notification types + quiet hours |
| **Sources** | Event source like/dislike controls |

Currently everything is on one long scrolling page. Each tab renders its own section; state is isolated per tab.

### Preferences tab: 3-step wizard

**Step 1 — Pick event types**

Chip-select grid of top-level event types. User toggles which ones they care about:

- Music, Sports, Arts & Theatre, Food & Drink, Comedy, Technology, Wellness, Outdoor, Family, Nightlife

Only types that are toggled on proceed to Step 2. At least one must be selected to advance.

**Step 2 — Rate base genres (per selected type)**

Cycles through each selected type one at a time. For each type, shows its base genres as sliders (same -1 to 5 weight scale as today, same label system: Not Interested → Low → Normal → Interested → Love it).

Genre groupings are defined frontend-side as a static map (since the DB categories are flat with no `parent_id`). Example for Music:

```
Music
  ├── Rock
  ├── Pop
  ├── Hip-Hop / Rap
  ├── Country
  ├── Jazz
  ├── Electronic / Dance
  ├── Classical
  ├── R&B / Soul
  ├── Folk / Americana
  ├── Metal
  ├── Blues
  └── Latin
```

Each genre slider maps to one or more existing category slugs in the DB. Saving writes weights for all mapped slugs.

Step 2 has Back / Next navigation. Progress indicator shows "Music · 1 of 3 types".

**Step 3 — Deep dive (optional, per positively-rated genre)**

Cycles through genres where weight > 1.0 (i.e. "Interested" or "Love it"), one at a time.

For each genre:

```
[Genre icon]  Want to go deeper on [Genre]?
              Select sub-genres and add favorite artists

Sub-genres: [chip grid — select/deselect]
Favorite artists (optional, max 3):
  [search input with MusicBrainz lookup]
  [matched artist chips with small metadata tag e.g. "Rock · UK"]

[Skip →]  [Save & Next →]
```

- User can add up to 3 artists per genre
- Artist search calls `GET https://musicbrainz.org/ws/2/artist?query={name}&fmt=json` (free, no key)
- On match: show artist name + primary genre tags from MusicBrainz as a confirmation chip
- On no match: show "Artist not found — save anyway?" option (free-text fallback)
- MusicBrainz genre tags are stored alongside the artist name for use in recommendation scoring
- Skipping a genre moves to the next without saving sub-genre/artist data for it

### Data model additions

Two new backend tables:

**`user_artist_preferences`**
```
user_id         UUID FK users
artist_name     TEXT
musicbrainz_id  TEXT nullable
mb_genres       TEXT[] nullable   -- genre tags from MusicBrainz
genre_context   TEXT              -- which base genre this was added under
weight          FLOAT DEFAULT 2.0
created_at      TIMESTAMPTZ
```

**`user_subgenre_preferences`**
```
user_id          UUID FK users
category_slug    TEXT FK categories.slug
weight           FLOAT
created_at       TIMESTAMPTZ
```

(Sub-genre preferences reuse the existing category weight system — `user_subgenre_preferences` is just a view alias; sub-genre slugs are already in the `categories` table and can be written directly via the existing `PUT /me/preferences` endpoint.)

So only `user_artist_preferences` is a truly new table.

### API additions

```
GET  /api/v1/me/artists                    # list user's saved artists
POST /api/v1/me/artists                    # add artist { artist_name, musicbrainz_id, mb_genres, genre_context }
DELETE /api/v1/me/artists/{artist_name}    # remove artist
```

MusicBrainz calls are made **from the frontend** directly (public API, no auth needed, no sensitive data). The backend only stores what the user confirms.

---

## Architecture Notes

### Frontend file changes summary

| File | Action |
|------|--------|
| `frontend/src/pages/Home.tsx` | Use home city, add seeding check |
| `frontend/src/components/CityLoadingScreen.tsx` | New — full-page loading state |
| `frontend/src/hooks/useCitySeeding.ts` | New — check/trigger/poll logic |
| `frontend/src/pages/Settings.tsx` | Add tab bar, split into tab components |
| `frontend/src/components/settings/PreferencesTab.tsx` | New — 3-step wizard |
| `frontend/src/components/settings/GeneralTab.tsx` | New — distance, city, timezone |
| `frontend/src/components/settings/NotificationsTab.tsx` | New — extracted from Settings.tsx |
| `frontend/src/components/settings/SourcesTab.tsx` | New — extracted from Settings.tsx |
| `frontend/src/api/client.ts` | Add ingest/city, artist preference endpoints |

### Backend file changes summary

| File | Action |
|------|--------|
| `backend/app/api/v1/seed.py` | Delete |
| `backend/app/ingestion/mock_data.py` | Delete |
| `backend/app/api/v1/ingest.py` | New — `POST /api/v1/ingest/city` |
| `backend/app/api/v1/me.py` | Add artist preference endpoints |
| `backend/app/models/` | Add `UserArtistPreference` model |
| `backend/worker/tasks/ingestion.py` | Add `ingest_city_now`, make city list dynamic |
| `backend/worker/celery_app.py` | Remove mock schedule entry |
| `backend/alembic/versions/` | New migration for `user_artist_preferences` |

### Error handling

- Ingest endpoint returns 200 immediately (fire-and-forget). Frontend doesn't wait.
- If MusicBrainz is unreachable, artist search shows "Can't verify right now — save anyway?" — never blocks the user.
- If city seeding times out (90s, 0 events), show actionable error with city search fallback.
- All existing preference save logic is preserved — wizard is additive, not a replacement for the underlying weight system.

---

## Out of Scope

- Artist-based event matching in the recommendation engine (store the data now, use it in a future spec)
- Venue-level preferences
- Social/shared preference profiles
- Auto-detecting city from browser geolocation (future)
