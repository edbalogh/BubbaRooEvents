import { useState } from 'react'
import { api } from '../api/client'

interface Source {
  id: number
  slug: string
  name: string
  source_type: string
  coverage_cities: string | null
  is_local: boolean
}

interface SourceRowProps {
  source: Source
  onRefreshed: () => void
}

export function SourceRow({ source, onRefreshed }: SourceRowProps) {
  const [refreshing, setRefreshing] = useState(false)
  const [refreshError, setRefreshError] = useState<string | null>(null)

  const handleRefresh = async (e: React.MouseEvent) => {
    e.preventDefault()
    setRefreshing(true)
    setRefreshError(null)
    try {
      const { job_id } = await api.refreshSource(source.slug)
      // Poll until done
      const poll = setInterval(async () => {
        const status = await api.getSourceRefreshStatus(source.slug, job_id)
        if (status.status === 'SUCCESS' || status.status === 'FAILURE') {
          clearInterval(poll)
          setRefreshing(false)
          if (status.status === 'FAILURE') setRefreshError(status.error ?? 'Failed')
          else onRefreshed()
        }
      }, 2000)
    } catch (err) {
      setRefreshing(false)
      setRefreshError(err instanceof Error ? err.message : 'Failed')
    }
  }

  return (
    <tr className="border-b border-gray-100 hover:bg-gray-50">
      <td className="py-3 px-4">
        <div className="font-medium text-gray-900">{source.name}</div>
        {source.is_local && (
          <span className="text-xs text-indigo-500 bg-indigo-50 px-1.5 py-0.5 rounded">local</span>
        )}
      </td>
      <td className="py-3 px-4 text-sm text-gray-500">{source.coverage_cities ?? 'All cities'}</td>
      <td className="py-3 px-4 text-sm text-gray-500">{source.source_type}</td>
      <td className="py-3 px-4">
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="text-sm px-3 py-1 bg-gray-100 hover:bg-brand-50 hover:text-brand-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
        {refreshError && <span className="text-xs text-red-500 ml-2">{refreshError}</span>}
      </td>
    </tr>
  )
}
