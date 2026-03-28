import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  api,
  type CategoryPreference,
  type CategoryInfo,
  type EventSourceInfo,
  type UserSourcePref,
} from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function Settings() {
  const { isAuthenticated, user } = useAuth()
  const [preferences, setPreferences] = useState<CategoryPreference[]>([])
  const [allCategories, setAllCategories] = useState<CategoryInfo[]>([])
  const [maxDistance, setMaxDistance] = useState(25)
  const [sources, setSources] = useState<EventSourceInfo[]>([])
  const [sourcePrefs, setSourcePrefs] = useState<Map<number, string>>(new Map())
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!isAuthenticated) return

    const load = async () => {
      try {
        const [prefs, cats, srcs, srcPrefs] = await Promise.all([
          api.getPreferences(),
          api.getCategories(),
          api.getSources(user?.home_city ?? undefined),
          api.getSourcePreferences(),
        ])
        setPreferences(prefs.categories)
        setMaxDistance(prefs.max_distance_miles)
        setAllCategories(cats)
        setSources(srcs)

        const prefMap = new Map<number, string>()
        srcPrefs.forEach((sp) => prefMap.set(sp.source_id, sp.preference))
        setSourcePrefs(prefMap)
      } catch (err) {
        console.error('Failed to load preferences:', err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [isAuthenticated, user?.home_city])

  if (!isAuthenticated) {
    return (
      <div className="text-center py-16">
        <p className="text-gray-500">Sign in to manage your preferences</p>
        <Link to="/login" className="text-brand-600 hover:underline mt-2 inline-block">Sign in</Link>
      </div>
    )
  }

  const getWeight = (slug: string) => {
    return preferences.find((p) => p.category_slug === slug)?.weight ?? 1.0
  }

  const setWeight = (slug: string, weight: number) => {
    setPreferences((prev) => {
      const existing = prev.find((p) => p.category_slug === slug)
      if (existing) {
        return prev.map((p) => (p.category_slug === slug ? { ...p, weight } : p))
      }
      const cat = allCategories.find((c) => c.slug === slug)
      return [...prev, {
        category_id: cat?.id ?? 0,
        category_name: cat?.name ?? slug,
        category_slug: slug,
        weight,
      }]
    })
  }

  const handleSourcePref = async (sourceId: number, preference: string) => {
    try {
      await api.updateSourcePreference(sourceId, preference)
      setSourcePrefs((prev) => {
        const next = new Map(prev)
        if (preference === 'neutral') {
          next.delete(sourceId)
        } else {
          next.set(sourceId, preference)
        }
        return next
      })
    } catch (err) {
      console.error('Failed to update source preference:', err)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setMessage('')
    try {
      const updates = allCategories.map((cat) => ({
        category_slug: cat.slug,
        weight: getWeight(cat.slug),
      }))
      await api.updatePreferences(updates)
      await api.updateDistancePreference(maxDistance)
      setMessage('Preferences saved!')
      setTimeout(() => setMessage(''), 3000)
    } catch (err) {
      setMessage('Failed to save preferences')
    } finally {
      setSaving(false)
    }
  }

  const weightLabel = (w: number) => {
    if (w <= -0.5) return 'Not interested'
    if (w <= 0.5) return 'Low'
    if (w <= 1.5) return 'Normal'
    if (w <= 2.5) return 'Interested'
    return 'Love it'
  }

  const weightColor = (w: number) => {
    if (w <= -0.5) return 'text-red-500'
    if (w <= 0.5) return 'text-gray-400'
    if (w <= 1.5) return 'text-gray-600'
    if (w <= 2.5) return 'text-blue-600'
    return 'text-green-600'
  }

  const sourceTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      api: 'API',
      scraper: 'Local Site',
      ical: 'Calendar Feed',
      manual: 'Manual',
    }
    return labels[type] ?? type
  }

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto animate-pulse space-y-4">
        <div className="h-8 bg-gray-200 rounded w-1/3" />
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-12 bg-gray-200 rounded" />
        ))}
      </div>
    )
  }

  const localSources = sources.filter((s) => s.is_local)
  const nationalSources = sources.filter((s) => !s.is_local)

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-500 mt-1">Control your event sources and preferences</p>
      </div>

      {/* Event Sources */}
      <div className="bg-white rounded-xl border p-6 space-y-6">
        <div>
          <h2 className="text-lg font-semibold">Event Sources</h2>
          <p className="text-sm text-gray-500 mt-1">
            Choose which sources you want to see events from.
            Like sources you trust, or turn off ones you don't want.
          </p>
        </div>

        {/* Local Sources */}
        {localSources.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-brand-600 uppercase tracking-wide">
              Local Sources
            </h3>
            <p className="text-xs text-gray-400">
              Community sites, local venues, and city calendars - often the best stuff
            </p>
            {localSources.map((source) => (
              <SourceRow
                key={source.id}
                source={source}
                preference={sourcePrefs.get(source.id) ?? 'neutral'}
                onUpdate={handleSourcePref}
                typeLabel={sourceTypeLabel(source.source_type)}
              />
            ))}
          </div>
        )}

        {/* National Sources */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
            National Sources
          </h3>
          {nationalSources.map((source) => (
            <SourceRow
              key={source.id}
              source={source}
              preference={sourcePrefs.get(source.id) ?? 'neutral'}
              onUpdate={handleSourcePref}
              typeLabel={sourceTypeLabel(source.source_type)}
            />
          ))}
        </div>
      </div>

      {/* Category Preferences */}
      <div className="bg-white rounded-xl border p-6 space-y-4">
        <h2 className="text-lg font-semibold">Event Categories</h2>
        <p className="text-sm text-gray-500">
          Adjust the slider to tell us how much you like each type of event.
          These also learn automatically as you save and dismiss events.
        </p>

        <div className="space-y-4">
          {allCategories.map((cat) => {
            const weight = getWeight(cat.slug)
            return (
              <div key={cat.slug} className="flex items-center gap-4">
                <span className="w-32 text-sm font-medium text-gray-700">{cat.name}</span>
                <input
                  type="range"
                  min="-1"
                  max="5"
                  step="0.5"
                  value={weight}
                  onChange={(e) => setWeight(cat.slug, parseFloat(e.target.value))}
                  className="flex-1 accent-brand-600"
                />
                <span className={`w-28 text-sm text-right ${weightColor(weight)}`}>
                  {weightLabel(weight)}
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Distance Preference */}
      <div className="bg-white rounded-xl border p-6 space-y-4">
        <h2 className="text-lg font-semibold">Distance</h2>
        <p className="text-sm text-gray-500">How far are you willing to travel for an event?</p>
        <div className="flex items-center gap-4">
          <input
            type="range"
            min="5"
            max="200"
            step="5"
            value={maxDistance}
            onChange={(e) => setMaxDistance(parseInt(e.target.value))}
            className="flex-1 accent-brand-600"
          />
          <span className="w-24 text-sm font-medium text-gray-700 text-right">
            {maxDistance} miles
          </span>
        </div>
      </div>

      {/* Save */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-6 py-3 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 font-medium"
        >
          {saving ? 'Saving...' : 'Save Preferences'}
        </button>
        {message && (
          <span className={`text-sm ${message.includes('Failed') ? 'text-red-500' : 'text-green-600'}`}>
            {message}
          </span>
        )}
      </div>
    </div>
  )
}


function SourceRow({
  source,
  preference,
  onUpdate,
  typeLabel,
}: {
  source: EventSourceInfo
  preference: string
  onUpdate: (sourceId: number, preference: string) => void
  typeLabel: string
}) {
  const prefButtons = [
    { value: 'liked', label: 'Like', activeClass: 'bg-green-100 text-green-700 border-green-300' },
    { value: 'neutral', label: 'Neutral', activeClass: 'bg-gray-100 text-gray-700 border-gray-300' },
    { value: 'disliked', label: 'Dislike', activeClass: 'bg-orange-100 text-orange-700 border-orange-300' },
    { value: 'disabled', label: 'Off', activeClass: 'bg-red-100 text-red-600 border-red-300' },
  ]

  return (
    <div className={`flex items-center gap-3 p-3 rounded-lg border ${preference === 'disabled' ? 'opacity-50 bg-gray-50' : 'bg-white'}`}>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm text-gray-900">{source.name}</span>
          <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">
            {typeLabel}
          </span>
          {source.is_local && (
            <span className="text-xs px-1.5 py-0.5 bg-brand-50 text-brand-700 rounded">
              Local
            </span>
          )}
        </div>
        {source.description && (
          <p className="text-xs text-gray-400 mt-0.5 truncate">{source.description}</p>
        )}
      </div>
      <div className="flex gap-1">
        {prefButtons.map((btn) => (
          <button
            key={btn.value}
            onClick={() => onUpdate(source.id, btn.value)}
            className={`px-2 py-1 text-xs rounded border transition-colors ${
              preference === btn.value
                ? btn.activeClass
                : 'bg-white text-gray-400 border-gray-200 hover:border-gray-300'
            }`}
          >
            {btn.label}
          </button>
        ))}
      </div>
    </div>
  )
}
