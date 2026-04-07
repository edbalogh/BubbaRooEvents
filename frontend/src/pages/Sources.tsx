import { useState, useEffect } from 'react'
import { api, type EventSourceInfo } from '../api/client'
import { SourceRow } from '../components/SourceRow'
import { useAuth } from '../context/AuthContext'

export default function Sources() {
  const { isAuthenticated } = useAuth()
  const [sources, setSources] = useState<EventSourceInfo[]>([])
  const [discoveryStatus, setDiscoveryStatus] = useState<{
    last_new_source_discovered_at: string | null
    total_discovered_sources: number
  } | null>(null)
  const [discovering, setDiscovering] = useState(false)
  const [loading, setLoading] = useState(true)

  const loadData = async () => {
    try {
      const [srcs, status] = await Promise.all([
        api.getSources(),
        api.getDiscoveryStatus(),
      ])
      setSources(srcs)
      setDiscoveryStatus(status)
    } catch (err) {
      console.error('Failed to load sources:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [])

  const handleRunDiscovery = async () => {
    setDiscovering(true)
    try {
      await api.runDiscovery()
      setTimeout(async () => {
        await loadData()
        setDiscovering(false)
      }, 10000)
    } catch (err) {
      console.error('Discovery failed:', err)
      setDiscovering(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="text-gray-500">Loading sources...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Event Sources</h1>
          <p className="text-gray-500 mt-1">
            {sources.length} active sources · {discoveryStatus?.total_discovered_sources ?? 0} auto-discovered
          </p>
        </div>
        {isAuthenticated && (
          <button
            onClick={handleRunDiscovery}
            disabled={discovering}
            className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {discovering ? 'Discovering...' : 'Run Discovery'}
          </button>
        )}
      </div>

      {discoveryStatus?.last_new_source_discovered_at && (
        <p className="text-sm text-gray-400">
          Last discovery: {new Date(discoveryStatus.last_new_source_discovered_at).toLocaleString()}
        </p>
      )}

      {sources.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No sources registered yet. Run discovery to find local event sites.
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Source</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">City</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Type</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((source) => (
                <SourceRow key={source.slug} source={source} onRefreshed={loadData} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
