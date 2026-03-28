import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  api,
  type CategoryPreference,
  type CategoryInfo,
  type EventSourceInfo,
  type UserSourcePref,
  type NotificationChannel,
  type NotificationPrefs,
} from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function Settings() {
  const { isAuthenticated, user } = useAuth()
  const [preferences, setPreferences] = useState<CategoryPreference[]>([])
  const [allCategories, setAllCategories] = useState<CategoryInfo[]>([])
  const [maxDistance, setMaxDistance] = useState(25)
  const [sources, setSources] = useState<EventSourceInfo[]>([])
  const [sourcePrefs, setSourcePrefs] = useState<Map<number, string>>(new Map())
  const [channels, setChannels] = useState<NotificationChannel[]>([])
  const [notifPrefs, setNotifPrefs] = useState<NotificationPrefs>({
    quiet_hours_start: null,
    quiet_hours_end: null,
    max_per_day: 5,
    enabled_types: ['ticket_alert', 'tonight', 'weekly_digest', 'new_match'],
  })
  const [newChannelType, setNewChannelType] = useState('email')
  const [newChannelAddress, setNewChannelAddress] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!isAuthenticated) return

    const load = async () => {
      try {
        const [prefs, cats, srcs, srcPrefs, nChannels, nPrefs] = await Promise.all([
          api.getPreferences(),
          api.getCategories(),
          api.getSources(user?.home_city ?? undefined),
          api.getSourcePreferences(),
          api.getNotificationChannels(),
          api.getNotificationPreferences(),
        ])
        setPreferences(prefs.categories)
        setMaxDistance(prefs.max_distance_miles)
        setAllCategories(cats)
        setSources(srcs)
        setChannels(nChannels)
        setNotifPrefs(nPrefs)

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
      await api.updateNotificationPreferences(notifPrefs)
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

      {/* Notification Channels */}
      <div className="bg-white rounded-xl border p-6 space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Notification Channels</h2>
          <p className="text-sm text-gray-500 mt-1">
            Add channels to receive event notifications via email, SMS, Slack, or push.
          </p>
        </div>

        {/* Existing channels */}
        {channels.length > 0 && (
          <div className="space-y-2">
            {channels.map((ch) => (
              <div
                key={ch.id}
                className={`flex items-center gap-3 p-3 rounded-lg border ${
                  ch.is_active ? 'bg-white' : 'bg-gray-50 opacity-60'
                }`}
              >
                <span className="text-lg">
                  {ch.channel_type === 'email' ? '\u2709' : ch.channel_type === 'sms' ? '\uD83D\uDCF1' : ch.channel_type === 'slack' ? '#' : '\uD83D\uDD14'}
                </span>
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-gray-900 capitalize">
                    {ch.channel_type}
                  </span>
                  <p className="text-xs text-gray-500 truncate">{ch.channel_address}</p>
                </div>
                <button
                  onClick={async () => {
                    const result = await api.toggleNotificationChannel(ch.id)
                    setChannels((prev) =>
                      prev.map((c) => (c.id === ch.id ? { ...c, is_active: result.is_active } : c))
                    )
                  }}
                  className={`px-3 py-1 text-xs rounded border ${
                    ch.is_active
                      ? 'bg-green-50 text-green-700 border-green-200'
                      : 'bg-gray-100 text-gray-500 border-gray-200'
                  }`}
                >
                  {ch.is_active ? 'Active' : 'Paused'}
                </button>
                <button
                  onClick={async () => {
                    await api.removeNotificationChannel(ch.id)
                    setChannels((prev) => prev.filter((c) => c.id !== ch.id))
                  }}
                  className="text-red-400 hover:text-red-600 text-sm"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Add new channel */}
        <div className="flex gap-2 items-end">
          <div>
            <label className="text-xs text-gray-500 block mb-1">Type</label>
            <select
              value={newChannelType}
              onChange={(e) => setNewChannelType(e.target.value)}
              className="border rounded px-3 py-2 text-sm"
            >
              <option value="email">Email</option>
              <option value="sms">SMS</option>
              <option value="slack">Slack Webhook</option>
              <option value="push">Push Token</option>
            </select>
          </div>
          <div className="flex-1">
            <label className="text-xs text-gray-500 block mb-1">
              {newChannelType === 'email'
                ? 'Email address'
                : newChannelType === 'sms'
                  ? 'Phone number'
                  : newChannelType === 'slack'
                    ? 'Webhook URL'
                    : 'FCM Token'}
            </label>
            <input
              type="text"
              value={newChannelAddress}
              onChange={(e) => setNewChannelAddress(e.target.value)}
              placeholder={
                newChannelType === 'email'
                  ? 'you@example.com'
                  : newChannelType === 'sms'
                    ? '+15551234567'
                    : newChannelType === 'slack'
                      ? 'https://hooks.slack.com/...'
                      : 'FCM device token'
              }
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </div>
          <button
            onClick={async () => {
              if (!newChannelAddress.trim()) return
              try {
                const ch = await api.addNotificationChannel(newChannelType, newChannelAddress.trim())
                setChannels((prev) => [ch, ...prev])
                setNewChannelAddress('')
              } catch (err: any) {
                setMessage(err.message || 'Failed to add channel')
              }
            }}
            className="px-4 py-2 bg-brand-600 text-white text-sm rounded hover:bg-brand-700"
          >
            Add
          </button>
        </div>
      </div>

      {/* Notification Preferences */}
      <div className="bg-white rounded-xl border p-6 space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Notification Preferences</h2>
          <p className="text-sm text-gray-500 mt-1">
            Control what types of notifications you receive and when.
          </p>
        </div>

        {/* Notification types */}
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-gray-700">Notification Types</h3>
          {[
            { type: 'ticket_alert', label: 'Ticket Alerts', desc: 'When matching events go on sale' },
            { type: 'tonight', label: 'Tonight', desc: 'Events happening today in your area' },
            { type: 'new_match', label: 'New Matches', desc: 'High-score events we think you\'ll love' },
            { type: 'weekly_digest', label: 'Weekly Digest', desc: 'Top upcoming events each week' },
          ].map(({ type, label, desc }) => (
            <label key={type} className="flex items-center gap-3 p-2 rounded hover:bg-gray-50 cursor-pointer">
              <input
                type="checkbox"
                checked={notifPrefs.enabled_types.includes(type)}
                onChange={(e) => {
                  setNotifPrefs((prev) => ({
                    ...prev,
                    enabled_types: e.target.checked
                      ? [...prev.enabled_types, type]
                      : prev.enabled_types.filter((t) => t !== type),
                  }))
                }}
                className="accent-brand-600 w-4 h-4"
              />
              <div>
                <span className="text-sm font-medium text-gray-900">{label}</span>
                <p className="text-xs text-gray-400">{desc}</p>
              </div>
            </label>
          ))}
        </div>

        {/* Throttle */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">Daily Limit</h3>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min="1"
              max="20"
              value={notifPrefs.max_per_day}
              onChange={(e) => setNotifPrefs((prev) => ({ ...prev, max_per_day: parseInt(e.target.value) }))}
              className="flex-1 accent-brand-600"
            />
            <span className="w-32 text-sm text-gray-700 text-right">
              {notifPrefs.max_per_day} per day
            </span>
          </div>
        </div>

        {/* Quiet hours */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">Quiet Hours</h3>
          <p className="text-xs text-gray-400 mb-2">No notifications during these hours</p>
          <div className="flex items-center gap-3">
            <input
              type="time"
              value={notifPrefs.quiet_hours_start ?? '22:00'}
              onChange={(e) => setNotifPrefs((prev) => ({ ...prev, quiet_hours_start: e.target.value }))}
              className="border rounded px-3 py-2 text-sm"
            />
            <span className="text-sm text-gray-500">to</span>
            <input
              type="time"
              value={notifPrefs.quiet_hours_end ?? '08:00'}
              onChange={(e) => setNotifPrefs((prev) => ({ ...prev, quiet_hours_end: e.target.value }))}
              className="border rounded px-3 py-2 text-sm"
            />
          </div>
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
