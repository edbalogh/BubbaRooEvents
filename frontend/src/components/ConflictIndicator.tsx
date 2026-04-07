import { useState } from 'react'

interface ConflictEntry {
  source: string
  value: unknown
}

interface ConflictIndicatorProps {
  conflicts: ConflictEntry[] | undefined | null
  fieldLabel: string
}

export function ConflictIndicator({ conflicts, fieldLabel }: ConflictIndicatorProps) {
  const [visible, setVisible] = useState(false)

  if (!conflicts || conflicts.length < 2) return null

  return (
    <span
      className="relative inline-block ml-1"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      <span className="cursor-help text-xs text-gray-400 border border-gray-300 rounded-full px-1 select-none">
        ?
      </span>
      {visible && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 bg-gray-800 text-white text-xs rounded px-2 py-1.5 whitespace-nowrap z-10">
          <div className="font-semibold mb-1">{fieldLabel} across sources:</div>
          {conflicts.map((c) => (
            <div key={c.source}>{c.source}: {String(c.value)}</div>
          ))}
        </div>
      )}
    </span>
  )
}
