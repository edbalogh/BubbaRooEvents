import { useEffect, useState, useCallback } from 'react'
import { api, type Event } from '../api/client'
import SearchBar from '../components/SearchBar'
import EventList from '../components/EventList'

export default function Home() {
  const [events, setEvents] = useState<Event[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [searchParams, setSearchParams] = useState<Record<string, string>>({ city: 'Austin' })

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

  useEffect(() => {
    loadEvents(searchParams)
  }, [searchParams, loadEvents])

  const handleSearch = (params: { q?: string; city?: string; category?: string }) => {
    const newParams: Record<string, string> = {}
    if (params.q) newParams.q = params.q
    if (params.city) newParams.city = params.city
    if (params.category) newParams.category = params.category
    setSearchParams(newParams)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Discover Events</h1>
        <p className="text-gray-500 mt-1">Find concerts, shows, meetups, and more near you</p>
      </div>
      <SearchBar onSearch={handleSearch} />
      <EventList events={events} loading={loading} total={total} />
    </div>
  )
}
