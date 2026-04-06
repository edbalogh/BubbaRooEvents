import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { Event } from '../api/client'

const SOURCE_LABELS: Record<string, string> = {
  ticketmaster: 'Ticketmaster',
  eventbrite: 'Eventbrite',
  seatgeek: 'SeatGeek',
  bandsintown: 'Bandsintown',
  meetup: 'Meetup',
  do512: 'Do512',
  'mohawk-austin': 'Mohawk Austin',
}

function formatSource(slug: string): string {
  return SOURCE_LABELS[slug] ?? slug.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function formatPrice(min: number | null, max: number | null, currency: string): string {
  if (min === null && max === null) return 'Price TBD'
  if (min === 0 && (max === 0 || max === null)) return 'Free'
  if (min !== null && max !== null && min !== max) {
    return `$${min} - $${max}`
  }
  return `$${min ?? max}`
}

interface EventCardProps {
  event: Event
  showActions?: boolean
  onSave?: (eventId: string) => void
  onDismiss?: (eventId: string) => void
}

export default function EventCard({ event, showActions, onSave, onDismiss }: EventCardProps) {
  const [saved, setSaved] = useState(false)

  const handleSave = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setSaved(true)
    onSave?.(event.id)
  }

  const handleDismiss = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    onDismiss?.(event.id)
  }

  // wraps single source; slice/overflow ready for future multi-source support
  const sources = [event.source]
  const visibleSources = sources.slice(0, 2)
  const overflow = sources.length - visibleSources.length

  return (
    <Link
      to={`/events/${event.id}`}
      className="block bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden hover:shadow-md transition-shadow"
    >
      {event.image_url && (
        <img
          src={event.image_url}
          alt={event.title}
          className="w-full h-48 object-cover"
        />
      )}
      <div className="p-4 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-gray-900 line-clamp-2">{event.title}</h3>
        </div>
        <p className="text-sm text-brand-600 font-medium">
          {formatDate(event.starts_at)}
        </p>
        {event.venue_name && (
          <p className="text-sm text-gray-500">
            {event.venue_name}
            {event.city && ` \u00b7 ${event.city}, ${event.state ?? ''}`}
          </p>
        )}
        <div className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-300 flex-shrink-0" />
          {visibleSources.map((slug, i) => (
            <span
              key={slug}
              className={`text-xs ${i === 0 ? 'text-indigo-300' : 'text-slate-400'}`}
            >
              {i > 0 && <span className="text-slate-300 mr-1">·</span>}
              {formatSource(slug)}
            </span>
          ))}
          {overflow > 0 && (
            <span className="text-xs text-gray-400">+{overflow}</span>
          )}
        </div>
        <div className="flex items-center justify-between pt-1">
          <span className="text-sm font-medium text-gray-700">
            {formatPrice(event.price_min, event.price_max, event.currency)}
          </span>
          {event.categories.length > 0 && (
            <div className="flex gap-1">
              {event.categories.slice(0, 2).map((cat) => (
                <span
                  key={cat}
                  className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full text-xs"
                >
                  {cat}
                </span>
              ))}
            </div>
          )}
        </div>

        {showActions && (
          <div className="flex gap-2 pt-2 border-t border-gray-100">
            <button
              onClick={handleSave}
              className={`flex-1 text-sm py-1.5 rounded-lg transition-colors ${
                saved
                  ? 'bg-green-50 text-green-700 border border-green-200'
                  : 'bg-gray-50 text-gray-600 hover:bg-brand-50 hover:text-brand-700 border border-gray-200'
              }`}
            >
              {saved ? 'Saved!' : 'Save'}
            </button>
            <button
              onClick={handleDismiss}
              className="flex-1 text-sm py-1.5 rounded-lg bg-gray-50 text-gray-400 hover:bg-red-50 hover:text-red-500 border border-gray-200 transition-colors"
            >
              Not interested
            </button>
          </div>
        )}
      </div>
    </Link>
  )
}
