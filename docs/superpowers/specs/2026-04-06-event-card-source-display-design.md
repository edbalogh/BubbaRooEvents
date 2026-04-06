# Event Card Source Display

**Date:** 2026-04-06
**Status:** Approved

## Summary

Add a source attribution row to each event card so users can see where an event came from. The row is designed to handle multiple sources when event deduplication is added in the future.

## Approach

Frontend-only change using a static slug-to-display-name lookup map. No backend changes, no API changes. The `source` field already exists on every `Event` object.

## Components Changed

- `frontend/src/components/EventCard.tsx` — only file modified

## Implementation Details

### SOURCE_LABELS map

A constant defined at the top of `EventCard.tsx` mapping known slugs to human-readable names:

```ts
const SOURCE_LABELS: Record<string, string> = {
  ticketmaster: 'Ticketmaster',
  eventbrite: 'Eventbrite',
  seatgeek: 'SeatGeek',
  bandsintown: 'Bandsintown',
  meetup: 'Meetup',
  do512: 'Do512',
  'mohawk-austin': 'Mohawk Austin',
}
```

Unknown slugs fall back to title-casing: `"my-venue"` → `"My Venue"`.

### formatSource helper

```ts
function formatSource(slug: string): string {
  return SOURCE_LABELS[slug] ?? slug.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}
```

### Source row placement

Inserted between the venue/city line and the price/categories row:

```
Jazz in the Park
Sat, Apr 12 · 7:00 PM
Zilker Park · Austin, TX
● Eventbrite                        ← new row
Free                    [Music]
```

### Rendering rules

- **Single source (current):** `● Ticketmaster` — colored dot + display name
- **Multiple sources (future):** `● Eventbrite · Ticketmaster +1` — show as many as fit, overflow as `+N`
- The component accepts `sources: string[]` internally (wrapping the single `event.source` in an array), so multi-source support requires no structural change later.

### Visual spec

| Element | Value |
|---|---|
| Dot color | `#a5b4fc` (indigo-300) |
| First source text | `text-xs text-indigo-300` |
| Additional sources | `text-xs text-slate-400` |
| Overflow `+N` | `text-xs text-gray-400` |
| Dot size | `6×6px`, `rounded-full` |
| Row gap | `gap-1`, `items-center` |

## Out of Scope

- Backend changes
- Event deduplication / merging
- Source filtering by source on the events list
