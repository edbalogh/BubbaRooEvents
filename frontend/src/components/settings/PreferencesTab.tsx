import { useState } from 'react'
import { api, type CategoryPreference, type ArtistPreference, type MusicBrainzArtist } from '../../api/client'
import { EVENT_TYPE_MAP, type GenreEntry } from './genreMap'

type WizardStep = 'types' | 'genres' | 'deepdive' | 'done'

function weightLabel(w: number): string {
  if (w <= -0.5) return 'Not interested'
  if (w <= 0.5) return 'Low'
  if (w <= 1.5) return 'Normal'
  if (w <= 2.5) return 'Interested'
  return 'Love it'
}

function weightColor(w: number): string {
  if (w <= -0.5) return 'text-red-500'
  if (w <= 0.5) return 'text-gray-400'
  if (w <= 1.5) return 'text-gray-600'
  if (w <= 2.5) return 'text-blue-600'
  return 'text-green-600'
}

interface PreferencesTabProps {
  initialPreferences: CategoryPreference[]
  onSaved: () => void
}

export default function PreferencesTab({ initialPreferences, onSaved }: PreferencesTabProps) {
  const [step, setStep] = useState<WizardStep>('types')
  const [selectedTypes, setSelectedTypes] = useState<string[]>([])
  const [typeIndex, setTypeIndex] = useState(0)
  const [weights, setWeights] = useState<Record<string, number>>(() => {
    const map: Record<string, number> = {}
    initialPreferences.forEach((p) => { map[p.category_slug] = p.weight })
    return map
  })
  const [deepdiveGenres, setDeepdiveGenres] = useState<GenreEntry[]>([])
  const [deepdiveIndex, setDeepdiveIndex] = useState(0)
  const [selectedSubGenres, setSelectedSubGenres] = useState<Record<string, string[]>>({})
  const [artistSearch, setArtistSearch] = useState('')
  const [artistResults, setArtistResults] = useState<MusicBrainzArtist[]>([])
  const [addedArtists, setAddedArtists] = useState<Record<string, ArtistPreference[]>>({})
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  const getWeight = (slug: string) => weights[slug] ?? 1.0
  const setWeight = (slug: string, w: number) => setWeights((prev) => ({ ...prev, [slug]: w }))

  // Step 1 handlers
  const toggleType = (label: string) => {
    setSelectedTypes((prev) =>
      prev.includes(label) ? prev.filter((t) => t !== label) : [...prev, label]
    )
  }

  const handleTypesNext = () => {
    if (selectedTypes.length === 0) return
    setTypeIndex(0)
    setStep('genres')
  }

  // Step 2 handlers
  const currentType = EVENT_TYPE_MAP.find((t) => t.label === selectedTypes[typeIndex])

  const handleGenresNext = async () => {
    if (typeIndex < selectedTypes.length - 1) {
      setTypeIndex((i) => i + 1)
    } else {
      // Save all genre weights before moving to deep dive
      setSaving(true)
      try {
        const updates = Object.entries(weights).map(([category_slug, weight]) => ({ category_slug, weight }))
        await api.updatePreferences(updates)
      } catch (err) {
        setMessage(err instanceof Error ? err.message : 'Failed to save preferences')
        setSaving(false)
        return
      } finally {
        setSaving(false)
      }
      // Build deep-dive list: genres from selected types where weight > 1.0 and subGenreSlugs exist
      const genres: GenreEntry[] = []
      EVENT_TYPE_MAP.filter((t) => selectedTypes.includes(t.label)).forEach((t) => {
        t.genres.forEach((g) => {
          const maxWeight = Math.max(...g.slugs.map((s) => getWeight(s)))
          if (maxWeight > 1.0 && g.subGenreSlugs && g.subGenreSlugs.length > 0) {
            genres.push(g)
          }
        })
      })
      setDeepdiveGenres(genres)
      setDeepdiveIndex(0)
      setStep(genres.length > 0 ? 'deepdive' : 'done')
    }
  }

  // Step 3 handlers
  const currentDeepGenre = deepdiveGenres[deepdiveIndex]

  const toggleSubGenre = (genreLabel: string, slug: string) => {
    setSelectedSubGenres((prev) => {
      const current = prev[genreLabel] ?? []
      return {
        ...prev,
        [genreLabel]: current.includes(slug) ? current.filter((s) => s !== slug) : [...current, slug],
      }
    })
  }

  const handleArtistSearch = async (query: string) => {
    setArtistSearch(query)
    if (query.length < 2) { setArtistResults([]); return }
    const results = await api.searchMusicBrainzArtists(query)
    setArtistResults(results)
  }

  const handleAddArtist = async (artist: MusicBrainzArtist, genreLabel: string) => {
    const current = addedArtists[genreLabel] ?? []
    if (current.length >= 3) return
    try {
      const saved = await api.addArtist({
        artist_name: artist.name,
        musicbrainz_id: artist.id,
        mb_genres: artist.tags?.slice(0, 5).map((t) => t.name) ?? [],
        genre_context: genreLabel.toLowerCase(),
      })
      setAddedArtists((prev) => ({ ...prev, [genreLabel]: [...(prev[genreLabel] ?? []), saved] }))
      setArtistSearch('')
      setArtistResults([])
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Failed to add artist')
    }
  }

  const handleDeepDiveSave = async () => {
    if (!currentDeepGenre) return
    // Save sub-genre weights (boost selected sub-genres to "Interested" if not already higher)
    const subSlugs = selectedSubGenres[currentDeepGenre.label] ?? []
    if (subSlugs.length > 0) {
      const updates = subSlugs.map((slug) => ({
        category_slug: slug,
        weight: Math.max(getWeight(slug), 2.0),
      }))
      await api.updatePreferences(updates)
    }
    handleDeepDiveNext()
  }

  const handleDeepDiveNext = () => {
    if (deepdiveIndex < deepdiveGenres.length - 1) {
      setDeepdiveIndex((i) => i + 1)
      setArtistSearch('')
      setArtistResults([])
    } else {
      setStep('done')
    }
  }

  // Step indicators
  const stepNum = step === 'types' ? 1 : step === 'genres' ? 2 : 3
  const stepLabels = ['Pick Types', 'Rate Genres', 'Go Deeper']

  if (step === 'done') {
    return (
      <div className="text-center py-16 space-y-4">
        <div className="text-5xl">🎉</div>
        <h2 className="text-xl font-semibold text-gray-900">Preferences saved!</h2>
        <p className="text-gray-500 text-sm">We'll use these to find events you'll love.</p>
        <button onClick={onSaved} className="px-6 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 text-sm">
          Done
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Step indicator */}
      <div className="flex items-center gap-2">
        {stepLabels.map((label, i) => (
          <div key={label} className="flex items-center gap-2">
            <div className={`w-6 h-6 rounded-full text-xs flex items-center justify-center font-medium ${i + 1 <= stepNum ? 'bg-brand-600 text-white' : 'bg-gray-200 text-gray-500'}`}>
              {i + 1}
            </div>
            <span className={`text-xs ${i + 1 === stepNum ? 'text-brand-600 font-medium' : 'text-gray-400'}`}>{label}</span>
            {i < stepLabels.length - 1 && <div className={`flex-1 h-0.5 w-8 ${i + 1 < stepNum ? 'bg-brand-600' : 'bg-gray-200'}`} />}
          </div>
        ))}
      </div>

      {/* Step 1: Pick types */}
      {step === 'types' && (
        <div className="bg-white rounded-xl border p-6 space-y-4">
          <h2 className="text-lg font-semibold">What types of events do you enjoy?</h2>
          <p className="text-sm text-gray-500">Select all that apply. You can always change this later.</p>
          <div className="flex flex-wrap gap-3">
            {EVENT_TYPE_MAP.map((type) => (
              <button
                key={type.label}
                onClick={() => toggleType(type.label)}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-colors border ${selectedTypes.includes(type.label) ? 'bg-brand-600 text-white border-brand-600' : 'bg-white text-gray-700 border-gray-200 hover:border-brand-300'}`}
              >
                {type.emoji} {type.label}
              </button>
            ))}
          </div>
          <div className="flex justify-end pt-2">
            <button
              onClick={handleTypesNext}
              disabled={selectedTypes.length === 0}
              className="px-6 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-40 text-sm font-medium"
            >
              Next →
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Rate genres */}
      {step === 'genres' && currentType && (
        <div className="bg-white rounded-xl border p-6 space-y-4">
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">
              {currentType.emoji} {currentType.label} · {typeIndex + 1} of {selectedTypes.length}
            </p>
            <h2 className="text-lg font-semibold">How much do you like each genre?</h2>
            <p className="text-sm text-gray-500">Slide to set your interest level.</p>
          </div>
          <div className="space-y-5">
            {currentType.genres.map((genre) => {
              const representativeSlug = genre.slugs[0] ?? genre.label.toLowerCase()
              const w = getWeight(representativeSlug)
              return (
                <div key={genre.label} className="space-y-1">
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium text-gray-700">{genre.label}</span>
                    <span className={`text-xs ${weightColor(w)}`}>{weightLabel(w)}</span>
                  </div>
                  <input
                    type="range"
                    min="-1"
                    max="3"
                    step="0.5"
                    value={w}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value)
                      genre.slugs.forEach((slug) => setWeight(slug, val))
                    }}
                    className="w-full accent-brand-600"
                  />
                </div>
              )
            })}
          </div>
          <div className="flex justify-between pt-2">
            <button onClick={() => { if (typeIndex > 0) setTypeIndex((i) => i - 1); else setStep('types') }}
              className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">
              ← Back
            </button>
            <button onClick={handleGenresNext} disabled={saving}
              className="px-6 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-40 text-sm font-medium">
              {saving ? 'Saving…' : typeIndex < selectedTypes.length - 1 ? 'Next →' : 'Continue →'}
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Deep dive */}
      {step === 'deepdive' && currentDeepGenre && (
        <div className="bg-white rounded-xl border p-6 space-y-5">
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">
              Optional · {deepdiveIndex + 1} of {deepdiveGenres.length}
            </p>
            <h2 className="text-lg font-semibold">Go deeper on {currentDeepGenre.label}?</h2>
            <p className="text-sm text-gray-500">Select sub-genres and add favorite artists (max 3).</p>
          </div>

          {/* Sub-genres */}
          {currentDeepGenre.subGenreSlugs && currentDeepGenre.subGenreSlugs.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-gray-500 uppercase">Sub-genres</p>
              <div className="flex flex-wrap gap-2">
                {currentDeepGenre.subGenreSlugs.map((slug) => {
                  const selected = (selectedSubGenres[currentDeepGenre.label] ?? []).includes(slug)
                  return (
                    <button
                      key={slug}
                      onClick={() => toggleSubGenre(currentDeepGenre.label, slug)}
                      className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors border ${selected ? 'bg-brand-600 text-white border-brand-600' : 'bg-white text-gray-600 border-gray-200 hover:border-brand-300'}`}
                    >
                      {slug.replace(/-/g, ' ').replace(/\//g, ' / ')}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Artist search */}
          <div className="space-y-2">
            <p className="text-xs font-medium text-gray-500 uppercase">
              Favorite Artists (optional · {(addedArtists[currentDeepGenre.label] ?? []).length}/3)
            </p>
            {(addedArtists[currentDeepGenre.label] ?? []).map((a) => (
              <div key={a.artist_name} className="flex items-center gap-2 bg-brand-50 border border-brand-200 rounded-full px-3 py-1 text-sm text-brand-700 w-fit">
                <span>{a.artist_name}</span>
                {a.mb_genres && a.mb_genres.length > 0 && (
                  <span className="text-xs text-brand-400">· {a.mb_genres.slice(0, 2).join(', ')}</span>
                )}
              </div>
            ))}
            {(addedArtists[currentDeepGenre.label] ?? []).length < 3 && (
              <div className="relative">
                <input
                  type="text"
                  value={artistSearch}
                  onChange={(e) => handleArtistSearch(e.target.value)}
                  placeholder="Search for an artist…"
                  className="border rounded-lg px-3 py-2 text-sm w-full"
                />
                {artistResults.length > 0 && (
                  <div className="absolute top-full left-0 right-0 bg-white border rounded-lg shadow-lg mt-1 z-10 overflow-hidden">
                    {artistResults.map((a) => (
                      <button
                        key={a.id}
                        onClick={() => handleAddArtist(a, currentDeepGenre.label)}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center justify-between"
                      >
                        <span>{a.name}</span>
                        {a.tags && a.tags.length > 0 && (
                          <span className="text-xs text-gray-400">{a.tags.slice(0, 2).map((t) => t.name).join(', ')}</span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {message && <p className="text-sm text-red-500">{message}</p>}

          <div className="flex justify-between pt-2">
            <button onClick={handleDeepDiveNext} className="px-4 py-2 text-sm text-gray-500 border rounded-lg hover:bg-gray-50">
              Skip →
            </button>
            <button onClick={handleDeepDiveSave}
              className="px-6 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 text-sm font-medium">
              {deepdiveIndex < deepdiveGenres.length - 1 ? 'Save & Next →' : 'Finish →'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
