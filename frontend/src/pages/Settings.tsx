import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type CategoryPreference, type EventSourceInfo, type NotificationChannel, type NotificationPrefs } from '../api/client'
import { useAuth } from '../context/AuthContext'
import GeneralTab from '../components/settings/GeneralTab'
import PreferencesTab from '../components/settings/PreferencesTab'
import NotificationsTab from '../components/settings/NotificationsTab'
import SourcesTab from '../components/settings/SourcesTab'

type Tab = 'general' | 'preferences' | 'notifications' | 'sources'

const TABS: { id: Tab; label: string }[] = [
  { id: 'general', label: 'General' },
  { id: 'preferences', label: 'Preferences' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'sources', label: 'Sources' },
]

export default function Settings() {
  const { isAuthenticated, user } = useAuth()
  const [activeTab, setActiveTab] = useState<Tab>('general')

  // Shared state
  const [preferences, setPreferences] = useState<CategoryPreference[]>([])
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
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!isAuthenticated) return
    const load = async () => {
      try {
        const [prefs, srcs, srcPrefs, nChannels, nPrefs] = await Promise.all([
          api.getPreferences(),
          api.getSources(user?.home_city ?? undefined),
          api.getSourcePreferences(),
          api.getNotificationChannels(),
          api.getNotificationPreferences(),
        ])
        setPreferences(prefs.categories)
        setMaxDistance(prefs.max_distance_miles)
        setSources(srcs)
        setChannels(nChannels)
        setNotifPrefs(nPrefs)
        const prefMap = new Map<number, string>()
        srcPrefs.forEach((sp) => prefMap.set(sp.source_id, sp.preference))
        setSourcePrefs(prefMap)
      } catch (err) {
        console.error('Failed to load settings:', err)
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

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto animate-pulse space-y-4">
        <div className="h-8 bg-gray-200 rounded w-1/3" />
        {Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-12 bg-gray-200 rounded" />)}
      </div>
    )
  }

  const handleSaveGeneral = async () => {
    setSaving(true)
    setMessage('')
    try {
      await api.updateDistancePreference(maxDistance)
      setMessage('Saved!')
      setTimeout(() => setMessage(''), 3000)
    } catch {
      setMessage('Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const handleSaveNotifications = async () => {
    setSaving(true)
    setMessage('')
    try {
      await api.updateNotificationPreferences(notifPrefs)
      setMessage('Saved!')
      setTimeout(() => setMessage(''), 3000)
    } catch {
      setMessage('Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const handleSourcePref = async (sourceId: number, preference: string) => {
    await api.updateSourcePreference(sourceId, preference)
    setSourcePrefs((prev) => {
      const next = new Map(prev)
      if (preference === 'neutral') next.delete(sourceId)
      else next.set(sourceId, preference)
      return next
    })
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-500 mt-1">Control your event sources and preferences</p>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-gray-200">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeTab === tab.id
                ? 'text-brand-600 border-brand-600'
                : 'text-gray-500 border-transparent hover:text-gray-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'general' && (
        <GeneralTab
          maxDistance={maxDistance}
          onMaxDistanceChange={setMaxDistance}
          onSave={handleSaveGeneral}
          saving={saving}
          message={message}
        />
      )}
      {activeTab === 'preferences' && (
        <PreferencesTab
          initialPreferences={preferences}
          onSaved={() => setActiveTab('general')}
        />
      )}
      {activeTab === 'notifications' && (
        <NotificationsTab
          channels={channels}
          setChannels={setChannels}
          notifPrefs={notifPrefs}
          setNotifPrefs={setNotifPrefs}
          onSave={handleSaveNotifications}
          saving={saving}
          message={message}
        />
      )}
      {activeTab === 'sources' && (
        <SourcesTab
          sources={sources}
          sourcePrefs={sourcePrefs}
          onUpdate={handleSourcePref}
        />
      )}
    </div>
  )
}
