import type { Event } from '../api/client'

interface CityLoadingScreenProps {
  city: string
  events: Event[]
  eventCount: number
  isError: boolean
}

export default function CityLoadingScreen({ city, events, eventCount, isError }: CityLoadingScreenProps) {
  const progress = Math.min(100, (eventCount / 10) * 100)

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
        <div className="text-4xl mb-4">😕</div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          Couldn't find events for {city}
        </h2>
        <p className="text-gray-500 text-sm">
          We couldn't load events right now. Try searching for another city.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4 space-y-6 max-w-md mx-auto">
      <div className="text-5xl">🎉</div>

      <div>
        <h2 className="text-2xl font-bold text-gray-900">Setting up {city} for you</h2>
        <p className="text-gray-500 mt-1 text-sm">Finding the best events in your city…</p>
      </div>

      <div className="w-full space-y-2">
        <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
          <div
            className="h-2 rounded-full bg-brand-600 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
        <p className="text-sm text-gray-500">
          {eventCount > 0 ? `${eventCount} events found` : 'Searching…'}
        </p>
      </div>

      {events.length > 0 && (
        <div className="w-full text-left bg-gray-50 rounded-xl p-4 space-y-2">
          {events.slice(0, 5).map((e) => (
            <div key={e.id} className="text-sm text-gray-700 flex items-start gap-2">
              <span className="text-green-500 mt-0.5">✓</span>
              <span>{e.title}</span>
            </div>
          ))}
          {eventCount > 5 && (
            <div className="text-sm text-gray-400 flex items-center gap-2">
              <span className="animate-pulse">⏳</span>
              <span>Finding more…</span>
            </div>
          )}
        </div>
      )}

      <p className="text-xs text-gray-400">This usually takes under a minute</p>
    </div>
  )
}
