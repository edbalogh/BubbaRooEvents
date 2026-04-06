import React, { useState } from 'react'
import { api, type NotificationChannel, type NotificationPrefs } from '../../api/client'

interface NotificationsTabProps {
  channels: NotificationChannel[]
  setChannels: React.Dispatch<React.SetStateAction<NotificationChannel[]>>
  notifPrefs: NotificationPrefs
  setNotifPrefs: React.Dispatch<React.SetStateAction<NotificationPrefs>>
  onSave: () => Promise<void>
  saving: boolean
  message: string
}

export default function NotificationsTab({
  channels, setChannels, notifPrefs, setNotifPrefs, onSave, saving, message,
}: NotificationsTabProps) {
  const [newChannelType, setNewChannelType] = useState('email')
  const [newChannelAddress, setNewChannelAddress] = useState('')

  return (
    <div className="space-y-6">
      {/* Notification Channels */}
      <div className="bg-white rounded-xl border p-6 space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Notification Channels</h2>
          <p className="text-sm text-gray-500 mt-1">Add channels to receive event notifications.</p>
        </div>
        {channels.length > 0 && (
          <div className="space-y-2">
            {channels.map((ch) => (
              <div key={ch.id} className={`flex items-center gap-3 p-3 rounded-lg border ${ch.is_active ? 'bg-white' : 'bg-gray-50 opacity-60'}`}>
                <span className="text-lg">{ch.channel_type === 'email' ? '✉' : ch.channel_type === 'sms' ? '📱' : ch.channel_type === 'slack' ? '#' : '🔔'}</span>
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-gray-900 capitalize">{ch.channel_type}</span>
                  <p className="text-xs text-gray-500 truncate">{ch.channel_address}</p>
                </div>
                <button
                  onClick={async () => {
                    const result = await api.toggleNotificationChannel(ch.id)
                    setChannels((prev) => prev.map((c) => (c.id === ch.id ? { ...c, is_active: result.is_active } : c)))
                  }}
                  className={`px-3 py-1 text-xs rounded border ${ch.is_active ? 'bg-green-50 text-green-700 border-green-200' : 'bg-gray-100 text-gray-500 border-gray-200'}`}
                >
                  {ch.is_active ? 'Active' : 'Paused'}
                </button>
                <button
                  onClick={async () => { await api.removeNotificationChannel(ch.id); setChannels((prev) => prev.filter((c) => c.id !== ch.id)) }}
                  className="text-red-400 hover:text-red-600 text-sm"
                >Remove</button>
              </div>
            ))}
          </div>
        )}
        <div className="flex gap-2 items-end">
          <div>
            <label className="text-xs text-gray-500 block mb-1">Type</label>
            <select value={newChannelType} onChange={(e) => setNewChannelType(e.target.value)} className="border rounded px-3 py-2 text-sm">
              <option value="email">Email</option>
              <option value="sms">SMS</option>
              <option value="slack">Slack Webhook</option>
              <option value="push">Push Token</option>
            </select>
          </div>
          <div className="flex-1">
            <label className="text-xs text-gray-500 block mb-1">
              {newChannelType === 'email' ? 'Email address' : newChannelType === 'sms' ? 'Phone number' : newChannelType === 'slack' ? 'Webhook URL' : 'FCM Token'}
            </label>
            <input type="text" value={newChannelAddress} onChange={(e) => setNewChannelAddress(e.target.value)}
              placeholder={newChannelType === 'email' ? 'you@example.com' : newChannelType === 'sms' ? '+15551234567' : newChannelType === 'slack' ? 'https://hooks.slack.com/...' : 'FCM device token'}
              className="border rounded px-3 py-2 text-sm w-full" />
          </div>
          <button
            onClick={async () => {
              if (!newChannelAddress.trim()) return
              const ch = await api.addNotificationChannel(newChannelType, newChannelAddress.trim())
              setChannels((prev) => [ch, ...prev])
              setNewChannelAddress('')
            }}
            className="px-4 py-2 bg-brand-600 text-white text-sm rounded hover:bg-brand-700"
          >Add</button>
        </div>
      </div>

      {/* Notification Types */}
      <div className="bg-white rounded-xl border p-6 space-y-4">
        <h2 className="text-lg font-semibold">Notification Preferences</h2>
        <div className="space-y-3">
          {[
            { type: 'ticket_alert', label: 'Ticket Alerts', desc: 'When matching events go on sale' },
            { type: 'tonight', label: 'Tonight', desc: 'Events happening today in your area' },
            { type: 'new_match', label: 'New Matches', desc: "High-score events we think you'll love" },
            { type: 'weekly_digest', label: 'Weekly Digest', desc: 'Top upcoming events each week' },
          ].map(({ type, label, desc }) => (
            <label key={type} className="flex items-center gap-3 p-2 rounded hover:bg-gray-50 cursor-pointer">
              <input type="checkbox" checked={notifPrefs.enabled_types.includes(type)}
                onChange={(e) => setNotifPrefs((prev) => ({ ...prev, enabled_types: e.target.checked ? [...prev.enabled_types, type] : prev.enabled_types.filter((t) => t !== type) }))}
                className="accent-brand-600 w-4 h-4" />
              <div>
                <span className="text-sm font-medium text-gray-900">{label}</span>
                <p className="text-xs text-gray-400">{desc}</p>
              </div>
            </label>
          ))}
        </div>
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">Daily Limit</h3>
          <div className="flex items-center gap-4">
            <input type="range" min="1" max="20" value={notifPrefs.max_per_day}
              onChange={(e) => setNotifPrefs((prev) => ({ ...prev, max_per_day: parseInt(e.target.value) }))}
              className="flex-1 accent-brand-600" />
            <span className="w-32 text-sm text-gray-700 text-right">{notifPrefs.max_per_day} per day</span>
          </div>
        </div>
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">Quiet Hours</h3>
          <div className="flex items-center gap-3">
            <input type="time" value={notifPrefs.quiet_hours_start ?? '22:00'}
              onChange={(e) => setNotifPrefs((prev) => ({ ...prev, quiet_hours_start: e.target.value }))}
              className="border rounded px-3 py-2 text-sm" />
            <span className="text-sm text-gray-500">to</span>
            <input type="time" value={notifPrefs.quiet_hours_end ?? '08:00'}
              onChange={(e) => setNotifPrefs((prev) => ({ ...prev, quiet_hours_end: e.target.value }))}
              className="border rounded px-3 py-2 text-sm" />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button onClick={onSave} disabled={saving} className="px-6 py-3 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 font-medium">
          {saving ? 'Saving…' : 'Save'}
        </button>
        {message && <span className={`text-sm ${message.includes('Failed') ? 'text-red-500' : 'text-green-600'}`}>{message}</span>}
      </div>
    </div>
  )
}
