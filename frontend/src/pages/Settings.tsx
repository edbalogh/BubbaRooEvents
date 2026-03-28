import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type CategoryPreference, type CategoryInfo } from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function Settings() {
  const { isAuthenticated } = useAuth()
  const [preferences, setPreferences] = useState<CategoryPreference[]>([])
  const [allCategories, setAllCategories] = useState<CategoryInfo[]>([])
  const [maxDistance, setMaxDistance] = useState(25)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!isAuthenticated) return

    const load = async () => {
      try {
        const [prefs, cats] = await Promise.all([
          api.getPreferences(),
          api.getCategories(),
        ])
        setPreferences(prefs.categories)
        setMaxDistance(prefs.max_distance_miles)
        setAllCategories(cats)
      } catch (err) {
        console.error('Failed to load preferences:', err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [isAuthenticated])

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

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Preferences</h1>
        <p className="text-gray-500 mt-1">Tell us what you like so we can find better events for you</p>
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
