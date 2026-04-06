import { useState } from 'react'
import { api } from '../../api/client'
import { useAuth } from '../../context/AuthContext'

interface GeneralTabProps {
  maxDistance: number
  onMaxDistanceChange: (v: number) => void
  onSave: () => Promise<void>
  saving: boolean
  message: string
}

export default function GeneralTab({ maxDistance, onMaxDistanceChange, onSave, saving, message }: GeneralTabProps) {
  const { user, updateUser } = useAuth()
  const [cityInput, setCityInput] = useState(user?.home_city ?? '')
  const [cityMsg, setCityMsg] = useState('')

  const handleCitySave = async () => {
    if (!cityInput.trim()) return
    try {
      await api.updateHomeCity(cityInput.trim())
      updateUser({ home_city: cityInput.trim() })
      setCityMsg('City updated!')
      setTimeout(() => setCityMsg(''), 3000)
    } catch {
      setCityMsg('Failed to update city')
    }
  }

  return (
    <div className="space-y-6">
      {/* Home City */}
      <div className="bg-white rounded-xl border p-6 space-y-4">
        <h2 className="text-lg font-semibold">Home City</h2>
        <p className="text-sm text-gray-500">Your default city for event discovery.</p>
        <div className="flex gap-2">
          <input
            type="text"
            value={cityInput}
            onChange={(e) => setCityInput(e.target.value)}
            placeholder="e.g. Nashville"
            className="border rounded px-3 py-2 text-sm flex-1"
          />
          <button
            onClick={handleCitySave}
            className="px-4 py-2 bg-brand-600 text-white text-sm rounded hover:bg-brand-700"
          >
            Update
          </button>
        </div>
        {cityMsg && (
          <p className={`text-sm ${cityMsg.includes('Failed') ? 'text-red-500' : 'text-green-600'}`}>{cityMsg}</p>
        )}
      </div>

      {/* Distance */}
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
            onChange={(e) => onMaxDistanceChange(parseInt(e.target.value))}
            className="flex-1 accent-brand-600"
          />
          <span className="w-24 text-sm font-medium text-gray-700 text-right">
            {maxDistance} miles
          </span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button
          onClick={onSave}
          disabled={saving}
          className="px-6 py-3 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 font-medium"
        >
          {saving ? 'Saving…' : 'Save'}
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
