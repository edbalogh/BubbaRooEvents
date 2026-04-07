import { useEffect, useState, useCallback } from 'react'
import { api, type Event } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useCitySeeding } from '../hooks/useCitySeeding'
import SearchBar from '../components/SearchBar'
import EventList from '../components/EventList'
import CityLoadingScreen from '../components/CityLoadingScreen'
import { NewSourceBanner } from '../components/NewSourceBanner'

export default function Home() {
  const { user } = useAuth()
  const defaultCity = user?.home_city ?? 'Austin'

  const [events, setEvents] = useState<Event[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [searchParams, setSearchParams] = useState<Record<string, string>>({ city: defaultCity })
  const [newSourceCount, setNewSourceCount] = useState(0)
  const [bannerDismissed, setBannerDismissed] = useState(() => !!localStorage.getItem('new_sources_dismissed_at'))

  const { state: seedState, events: seedEvents, eventCount, city: seedCity } = useCitySeeding(defaultCity)

  useEffect(() => {
    api.getDiscoveryStatus().then((status) => {
      const dismissedAt = localStorage.getItem('new_sources_dismissed_at')
      if (
        status.last_new_source_discovered_at &&
        (!dismissedAt || new Date(status.last_new_source_discovered_at) > new Date(dismissedAt))
      ) {
        setNewSourceCount(status.total_discovered_sources)
      }
    }).catch(() => {/* ignore */})
  }, [])

  const loadEvents = useCallback(async (params: Record<string, string>) => {
    setLoading(true)
    try {
      const data = await api.searchEvents(params)
      setEvents(data.events)
      setTotal(data.total)
    } catch (err) {
      console.error('Failed to load events:', err)
      setEvents([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [])

  // Once seeding resolves to 'done', load the full event list
  useEffect(() => {
    if (seedState === 'done') {
      loadEvents(searchParams)
    }
  }, [seedState, searchParams, loadEvents])

  const handleSearch = (params: { q?: string; city?: string; category?: string }) => {
    const newParams: Record<string, string> = {}
    if (params.q) newParams.q = params.q
    newParams.city = params.city ?? defaultCity
    if (params.category) newParams.category = params.category
    setSearchParams(newParams)
  }

  // Show loading screen while seeding
  if (seedState === 'checking' || seedState === 'seeding') {
    return (
      <CityLoadingScreen
        city={seedCity}
        events={seedEvents}
        eventCount={eventCount}
        isError={false}
      />
    )
  }

  if (seedState === 'error') {
    return (
      <CityLoadingScreen
        city={seedCity}
        events={[]}
        eventCount={0}
        isError={true}
      />
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Discover Events</h1>
        <p className="text-gray-500 mt-1">
          Find concerts, shows, meetups, and more
          {defaultCity ? ` in ${defaultCity}` : ' near you'}
        </p>
      </div>
      {!bannerDismissed && newSourceCount > 0 && (
        <NewSourceBanner
          count={newSourceCount}
          onDismiss={() => {
            setBannerDismissed(true)
            localStorage.setItem('new_sources_dismissed_at', new Date().toISOString())
          }}
        />
      )}
      <SearchBar onSearch={handleSearch} initialCity={defaultCity} />
      <EventList events={events} loading={loading} total={total} />
    </div>
  )
}
