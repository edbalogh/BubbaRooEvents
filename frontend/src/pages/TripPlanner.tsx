import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import EventCard from '../components/EventCard'

interface TripEvent {
  id: string
  title: string
  description: string | null
  venue_name: string | null
  city: string | null
  starts_at: string | null
  price_min: number | null
  price_max: number | null
  url: string | null
  image_url: string | null
  score: number
  categories: string[]
}

interface TripResult {
  city: string
  dates: string
  plan: string
  events: TripEvent[]
  total_events: number
}

export default function TripPlanner() {
  const { isAuthenticated } = useAuth()
  const [city, setCity] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [interests, setInterests] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<TripResult | null>(null)
  const [error, setError] = useState('')

  if (!isAuthenticated) {
    return (
      <div className="text-center py-16">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Trip Planner</h2>
        <p className="text-gray-500">Sign in to plan your next adventure</p>
        <Link to="/login" className="text-brand-600 hover:underline mt-2 inline-block">Sign in</Link>
      </div>
    )
  }

  const handleExplore = async () => {
    if (!city.trim() || !dateFrom || !dateTo) {
      setError('Please fill in the city and dates')
      return
    }

    setLoading(true)
    setError('')
    setResult(null)

    try {
      const data = await api.exploreTrip({
        city: city.trim(),
        date_from: dateFrom,
        date_to: dateTo,
        interests: interests.trim() ? interests.split(',').map((s) => s.trim()) : undefined,
      })
      setResult(data)
    } catch (err: any) {
      setError(err.message || 'Failed to plan trip')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Trip Planner</h1>
        <p className="text-gray-500 mt-1">
          Discover events at your destination and get an AI-curated itinerary.
        </p>
      </div>

      {/* Search Form */}
      <div className="bg-white rounded-xl border p-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Destination City</label>
            <input
              type="text"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="Denver"
              className="w-full border rounded-lg px-4 py-2.5"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Arriving</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-full border rounded-lg px-4 py-2.5"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Leaving</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-full border rounded-lg px-4 py-2.5"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Interests <span className="text-gray-400">(optional, comma-separated)</span>
          </label>
          <input
            type="text"
            value={interests}
            onChange={(e) => setInterests(e.target.value)}
            placeholder="live music, food, comedy"
            className="w-full border rounded-lg px-4 py-2.5"
          />
        </div>

        <button
          onClick={handleExplore}
          disabled={loading}
          className="px-6 py-3 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 font-medium"
        >
          {loading ? 'Planning...' : 'Explore Events'}
        </button>

        {error && <p className="text-red-500 text-sm">{error}</p>}
      </div>

      {/* Results */}
      {result && (
        <>
          {/* AI Plan */}
          <div className="bg-gradient-to-br from-brand-50 to-blue-50 rounded-xl border border-brand-200 p-6">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-lg">&#x2728;</span>
              <h2 className="text-lg font-semibold text-brand-900">Your Trip Plan</h2>
            </div>
            <p className="text-sm text-gray-500 mb-3">{result.dates}</p>
            <div className="prose prose-sm max-w-none text-gray-800 whitespace-pre-line">
              {result.plan}
            </div>
          </div>

          {/* Event List */}
          <div>
            <h2 className="text-lg font-semibold mb-4">
              {result.total_events} Events in {result.city}
            </h2>
            {result.events.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {result.events.map((event) => (
                  <EventCard
                    key={event.id}
                    event={{
                      id: event.id,
                      source: '',
                      title: event.title,
                      description: event.description,
                      venue_name: event.venue_name,
                      venue_address: null,
                      city: event.city,
                      state: null,
                      country: 'US',
                      latitude: null,
                      longitude: null,
                      starts_at: event.starts_at ?? '',
                      ends_at: null,
                      on_sale_at: null,
                      price_min: event.price_min,
                      price_max: event.price_max,
                      currency: 'USD',
                      url: event.url,
                      image_url: event.image_url,
                      status: 'active',
                      categories: event.categories,
                    }}
                  />
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p>No events found for these dates yet.</p>
                <p className="text-sm mt-1">Try different dates or check back later!</p>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
