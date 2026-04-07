import { useState, useEffect } from 'react'
import { api, type CanonicalEventResponse } from '../api/client'

export default function Duplicates() {
  const [duplicates, setDuplicates] = useState<CanonicalEventResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [merging, setMerging] = useState<string | null>(null)

  const loadData = async () => {
    try {
      const data = await api.getFlaggedDuplicates()
      setDuplicates(data)
    } catch (err) {
      console.error('Failed to load duplicates:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [])

  const handleMerge = async (keepId: string, mergeId: string) => {
    setMerging(keepId)
    try {
      await api.mergeDuplicates(keepId, mergeId)
      await loadData()
    } catch (err) {
      console.error('Merge failed:', err)
    } finally {
      setMerging(null)
    }
  }

  if (loading) {
    return <div className="flex justify-center py-12"><div className="text-gray-500">Loading...</div></div>
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Flagged Duplicates</h1>
        <p className="text-gray-500 mt-1">
          Events flagged as potential duplicates. Merging keeps one canonical record and hides the other.
        </p>
      </div>

      {duplicates.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No flagged duplicates. Use the &quot;Report duplicate&quot; button on any event card to flag one.
        </div>
      ) : (
        <div className="space-y-4">
          {duplicates.map((dup) => (
            <div key={dup.id} className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <div className="flex items-start gap-6">
                <div className="flex-1">
                  <div className="text-xs text-gray-400 font-medium uppercase mb-1">Event A (flagged)</div>
                  <div className="font-semibold text-gray-900">{dup.title}</div>
                  <div className="text-sm text-gray-500 mt-0.5">
                    {dup.starts_at ? new Date(dup.starts_at).toLocaleString() : ''}
                  </div>
                  <div className="text-xs text-gray-400 mt-1 font-mono">{dup.id}</div>
                </div>
              </div>
              <div className="flex gap-3 mt-4 pt-4 border-t border-gray-100">
                <button
                  onClick={() => handleMerge(dup.id, dup.id)}
                  disabled={merging === dup.id}
                  className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700 disabled:opacity-50 transition-colors"
                >
                  {merging === dup.id ? 'Merging...' : 'Mark as reviewed (not duplicate)'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
