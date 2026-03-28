import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api, type Event } from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function EventDetail() {
  const { id } = useParams<{ id: string }>()
  const { isAuthenticated } = useAuth()
  const [event, setEvent] = useState<Event | null>(null)
  const [loading, setLoading] = useState(true)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    api.getEvent(id)
      .then(setEvent)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [id])

  const handleSave = async () => {
    if (!id) return
    try {
      if (saved) {
        await api.unsaveEvent(id)
        setSaved(false)
      } else {
        await api.saveEvent(id)
        setSaved(true)
      }
    } catch (err) {
      console.error('Failed to save event:', err)
    }
  }

  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-64 bg-gray-200 rounded-xl" />
        <div className="h-8 bg-gray-200 rounded w-2/3" />
        <div className="h-4 bg-gray-200 rounded w-1/3" />
      </div>
    )
  }

  if (!event) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 text-lg">Event not found</p>
        <Link to="/" className="text-brand-600 hover:underline mt-2 inline-block">
          Back to events
        </Link>
      </div>
    )
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })
  }

  return (
    <div className="max-w-3xl mx-auto">
      <Link to="/" className="text-brand-600 hover:underline text-sm mb-4 inline-block">
        &larr; Back to events
      </Link>

      {event.image_url && (
        <img
          src={event.image_url}
          alt={event.title}
          className="w-full h-72 object-cover rounded-xl mb-6"
        />
      )}

      <div className="space-y-4">
        <h1 className="text-3xl font-bold text-gray-900">{event.title}</h1>

        <div className="flex flex-wrap gap-2">
          {event.categories.map((cat) => (
            <span key={cat} className="px-3 py-1 bg-brand-50 text-brand-700 rounded-full text-sm">
              {cat}
            </span>
          ))}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 py-4 border-y border-gray-200">
          <div>
            <p className="text-sm text-gray-500">Date & Time</p>
            <p className="font-medium">{formatDate(event.starts_at)}</p>
            {event.ends_at && (
              <p className="text-sm text-gray-500">Ends: {formatDate(event.ends_at)}</p>
            )}
          </div>
          <div>
            <p className="text-sm text-gray-500">Venue</p>
            <p className="font-medium">{event.venue_name ?? 'TBD'}</p>
            {event.venue_address && <p className="text-sm text-gray-500">{event.venue_address}</p>}
            <p className="text-sm text-gray-500">
              {event.city}{event.state ? `, ${event.state}` : ''}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Price</p>
            <p className="font-medium">
              {event.price_min === 0 && (event.price_max === 0 || !event.price_max)
                ? 'Free'
                : event.price_min !== null
                  ? `$${event.price_min}${event.price_max ? ` - $${event.price_max}` : ''}`
                  : 'TBD'}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Source</p>
            <p className="font-medium capitalize">{event.source}</p>
          </div>
        </div>

        {event.description && (
          <div>
            <h2 className="text-lg font-semibold mb-2">About</h2>
            <p className="text-gray-700 leading-relaxed">{event.description}</p>
          </div>
        )}

        <div className="flex gap-3 pt-4">
          {event.url && (
            <a
              href={event.url}
              target="_blank"
              rel="noopener noreferrer"
              className="px-6 py-3 bg-brand-600 text-white rounded-lg hover:bg-brand-700 transition-colors font-medium"
            >
              Get Tickets
            </a>
          )}
          {isAuthenticated && (
            <button
              onClick={handleSave}
              className={`px-6 py-3 rounded-lg font-medium transition-colors ${
                saved
                  ? 'bg-green-100 text-green-700 border border-green-300'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-300'
              }`}
            >
              {saved ? 'Saved' : 'Save Event'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
