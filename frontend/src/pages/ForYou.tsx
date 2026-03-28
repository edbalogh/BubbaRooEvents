import { useEffect, useState, useCallback } from 'react'
import { api, type RecommendedEvent } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { Link } from 'react-router-dom'
import EventCard from '../components/EventCard'

export default function ForYou() {
  const { isAuthenticated, user } = useAuth()
  const [events, setEvents] = useState<RecommendedEvent[]>([])
  const [loading, setLoading] = useState(true)

  const loadRecommendations = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getRecommendations(
        user?.home_city ? { city: user.home_city } : undefined,
      )
      setEvents(data)
    } catch (err) {
      console.error('Failed to load recommendations:', err)
    } finally {
      setLoading(false)
    }
  }, [user?.home_city])

  useEffect(() => {
    if (isAuthenticated) {
      loadRecommendations()
    }
  }, [isAuthenticated, loadRecommendations])

  const handleDismiss = async (eventId: string) => {
    try {
      await api.logInteraction(eventId, 'dismissed')
      setEvents((prev) => prev.filter((e) => e.id !== eventId))
    } catch (err) {
      console.error('Failed to dismiss:', err)
    }
  }

  const handleSave = async (eventId: string) => {
    try {
      await api.saveEvent(eventId)
    } catch (err) {
      console.error('Failed to save:', err)
    }
  }

  if (!isAuthenticated) {
    return (
      <div className="text-center py-16">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Your Personalized Feed</h1>
        <p className="text-gray-500 mb-6">Sign in to get event recommendations tailored to your interests</p>
        <Link to="/login" className="bg-brand-600 text-white px-6 py-3 rounded-lg hover:bg-brand-700">
          Sign in to get started
        </Link>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">For You</h1>
          <p className="text-gray-500 mt-1">Events picked based on your interests</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl shadow-sm border animate-pulse">
              <div className="h-48 bg-gray-200 rounded-t-xl" />
              <div className="p-4 space-y-3">
                <div className="h-4 bg-gray-200 rounded w-3/4" />
                <div className="h-3 bg-gray-200 rounded w-1/2" />
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">For You</h1>
          <p className="text-gray-500 mt-1">
            Events picked based on your interests
            {user?.home_city && ` in ${user.home_city}`}
          </p>
        </div>
        <Link
          to="/settings"
          className="text-sm text-brand-600 hover:underline"
        >
          Adjust preferences
        </Link>
      </div>

      {events.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-xl border">
          <p className="text-gray-500 text-lg mb-2">No recommendations yet</p>
          <p className="text-gray-400 text-sm">
            Browse and save some events from the{' '}
            <Link to="/" className="text-brand-600 hover:underline">Discover</Link>{' '}
            page to train your preferences
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {events.map((event) => (
            <div key={event.id} className="relative group">
              <EventCard event={event} showActions onSave={handleSave} onDismiss={handleDismiss} />
              <div className="absolute top-2 right-2 bg-black/60 text-white text-xs px-2 py-1 rounded-full opacity-0 group-hover:opacity-100 transition-opacity">
                Match: {Math.round(event.score * 100)}%
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
