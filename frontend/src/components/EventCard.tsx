import { Link } from 'react-router-dom'
import type { Event } from '../api/client'

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

export default function EventCard({ event }: { event: Event }) {
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
      </div>
    </Link>
  )
}
