import { Link } from 'react-router-dom'

interface NewSourceBannerProps {
  count: number
  onDismiss: () => void
}

export function NewSourceBanner({ count, onDismiss }: NewSourceBannerProps) {
  if (count === 0) return null

  return (
    <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 flex items-center justify-between">
      <span className="text-sm text-green-800">
        <span className="font-medium">{count} new local event source{count > 1 ? 's' : ''}</span> discovered.{' '}
        <Link to="/sources" className="underline hover:text-green-900">View Sources →</Link>
      </span>
      <button
        onClick={onDismiss}
        className="text-green-600 hover:text-green-800 text-lg leading-none ml-4"
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  )
}
