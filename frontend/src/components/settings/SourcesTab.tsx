import type { EventSourceInfo } from '../../api/client'

interface SourcesTabProps {
  sources: EventSourceInfo[]
  sourcePrefs: Map<number, string>
  onUpdate: (sourceId: number, preference: string) => Promise<void>
}

function sourceTypeLabel(type: string): string {
  const labels: Record<string, string> = { api: 'API', scraper: 'Local Site', ical: 'Calendar Feed', manual: 'Manual' }
  return labels[type] ?? type
}

function SourceRow({ source, preference, onUpdate, typeLabel }: { source: EventSourceInfo; preference: string; onUpdate: (id: number, pref: string) => void; typeLabel: string }) {
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
          <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">{typeLabel}</span>
          {source.is_local && <span className="text-xs px-1.5 py-0.5 bg-brand-50 text-brand-700 rounded">Local</span>}
        </div>
        {source.description && <p className="text-xs text-gray-400 mt-0.5 truncate">{source.description}</p>}
      </div>
      <div className="flex gap-1">
        {prefButtons.map((btn) => (
          <button key={btn.value} onClick={() => onUpdate(source.id, btn.value)}
            className={`px-2 py-1 text-xs rounded border transition-colors ${preference === btn.value ? btn.activeClass : 'bg-white text-gray-400 border-gray-200 hover:border-gray-300'}`}>
            {btn.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function SourcesTab({ sources, sourcePrefs, onUpdate }: SourcesTabProps) {
  const localSources = sources.filter((s) => s.is_local)
  const nationalSources = sources.filter((s) => !s.is_local)

  return (
    <div className="bg-white rounded-xl border p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Event Sources</h2>
        <p className="text-sm text-gray-500 mt-1">Choose which sources you want to see events from.</p>
      </div>
      {localSources.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-brand-600 uppercase tracking-wide">Local Sources</h3>
          {localSources.map((s) => <SourceRow key={s.id} source={s} preference={sourcePrefs.get(s.id) ?? 'neutral'} onUpdate={onUpdate} typeLabel={sourceTypeLabel(s.source_type)} />)}
        </div>
      )}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">National Sources</h3>
        {nationalSources.map((s) => <SourceRow key={s.id} source={s} preference={sourcePrefs.get(s.id) ?? 'neutral'} onUpdate={onUpdate} typeLabel={sourceTypeLabel(s.source_type)} />)}
      </div>
    </div>
  )
}
