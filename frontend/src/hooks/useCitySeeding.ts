import { useState, useEffect, useRef } from 'react'
import { api, type Event } from '../api/client'

type SeedingState = 'checking' | 'seeding' | 'done' | 'error'

interface UseCitySeedingResult {
  state: SeedingState
  events: Event[]
  eventCount: number
  city: string
}

const POLL_INTERVAL_MS = 3000
const TIMEOUT_MS = 90000

export function useCitySeeding(city: string): UseCitySeedingResult {
  const [state, setState] = useState<SeedingState>('checking')
  const [events, setEvents] = useState<Event[]>([])
  const [eventCount, setEventCount] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const checkedCityRef = useRef<string | null>(null)

  useEffect(() => {
    if (!city || checkedCityRef.current === city) return
    checkedCityRef.current = city
    setState('checking')
    setEvents([])
    setEventCount(0)

    const cleanup = () => {
      if (timerRef.current) clearInterval(timerRef.current)
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }

    const checkAndSeed = async () => {
      try {
        // Check if city has events already
        const initial = await api.searchEvents({ city, per_page: '1' })
        if (initial.total > 0) {
          setEventCount(initial.total)
          setState('done')
          return
        }

        // No events — trigger ingestion and start polling
        setState('seeding')
        try {
          await api.ingestCity(city)
        } catch {
          // Ingest endpoint failure is non-fatal — still poll
        }

        // Timeout after 90s
        timeoutRef.current = setTimeout(() => {
          cleanup()
          setState('error')
        }, TIMEOUT_MS)

        // Poll every 3s for events
        timerRef.current = setInterval(async () => {
          try {
            const data = await api.searchEvents({ city, per_page: '5' })
            if (data.total > 0) {
              setEvents(data.events)
              setEventCount(data.total)
              cleanup()
              setState('done')
            }
          } catch {
            // ignore poll errors, keep trying
          }
        }, POLL_INTERVAL_MS)
      } catch {
        setState('error')
      }
    }

    checkAndSeed()
    return cleanup
  }, [city])

  return { state, events, eventCount, city }
}
