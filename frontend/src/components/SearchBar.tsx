import { useState } from 'react'

interface SearchBarProps {
  onSearch: (params: { q?: string; city?: string; category?: string }) => void
  initialCity?: string
}

const CATEGORIES = [
  { label: 'All', value: '' },
  { label: 'Concerts', value: 'music' },
  { label: 'Sports', value: 'sports' },
  { label: 'Conventions', value: 'conventions' },
  { label: 'Comedy', value: 'comedy' },
  { label: 'Theatre', value: 'theatre' },
  { label: 'Food & Drink', value: 'food' },
  { label: 'Festivals', value: 'festival' },
  { label: 'Tech', value: 'technology' },
  { label: 'Outdoor', value: 'outdoor' },
  { label: 'Fitness', value: 'fitness' },
  { label: 'Family', value: 'family' },
  { label: 'Nightlife', value: 'nightlife' },
]

export default function SearchBar({ onSearch, initialCity = '' }: SearchBarProps) {
  const [query, setQuery] = useState('')
  const [city, setCity] = useState(initialCity)
  const [activeCategory, setActiveCategory] = useState('')

  const handleSearch = () => {
    onSearch({
      q: query || undefined,
      city: city || undefined,
      category: activeCategory || undefined,
    })
  }

  const handleCategoryClick = (value: string) => {
    setActiveCategory(value)
    onSearch({
      q: query || undefined,
      city: city || undefined,
      category: value || undefined,
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Search events..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none"
        />
        <input
          type="text"
          placeholder="City"
          value={city}
          onChange={(e) => setCity(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="w-40 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none"
        />
        <button
          onClick={handleSearch}
          className="px-6 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 transition-colors"
        >
          Search
        </button>
      </div>
      <div className="flex gap-2 flex-wrap">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.value}
            onClick={() => handleCategoryClick(cat.value)}
            className={`px-3 py-1 rounded-full text-sm transition-colors ${
              activeCategory === cat.value
                ? 'bg-brand-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>
    </div>
  )
}
