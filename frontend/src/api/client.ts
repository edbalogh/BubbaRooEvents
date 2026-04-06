const BASE_URL = '/api/v1'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { ...headers, ...options?.headers },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

export interface Event {
  id: string
  source: string
  title: string
  description: string | null
  venue_name: string | null
  venue_address: string | null
  city: string | null
  state: string | null
  country: string
  latitude: number | null
  longitude: number | null
  starts_at: string
  ends_at: string | null
  on_sale_at: string | null
  price_min: number | null
  price_max: number | null
  currency: string
  url: string | null
  image_url: string | null
  status: string
  categories: string[]
}

export interface EventListResponse {
  events: Event[]
  total: number
  page: number
  per_page: number
}

export interface User {
  id: string
  email: string
  display_name: string
  home_city: string | null
  timezone: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface RecommendedEvent extends Event {
  score: number
  score_breakdown: {
    category_affinity: number
    embedding_similarity: number
    popularity: number
    distance_penalty: number
  }
}

export interface CategoryPreference {
  category_id: number
  category_name: string
  category_slug: string
  weight: number
}

export interface PreferencesResponse {
  categories: CategoryPreference[]
  max_distance_miles: number
}

export interface CategoryInfo {
  id: number
  name: string
  slug: string
  parent_id: number | null
}

export interface EventSourceInfo {
  id: number
  slug: string
  name: string
  source_type: string
  description: string | null
  url: string | null
  is_local: boolean
  coverage_cities: string | null
}

export interface UserSourcePref {
  source_id: number
  source_slug: string
  source_name: string
  source_type: string
  is_local: boolean
  preference: string  // liked, disliked, disabled
}

export interface NotificationChannel {
  id: string
  channel_type: string
  channel_address: string
  is_active: boolean
}

export interface NotificationPrefs {
  quiet_hours_start: string | null
  quiet_hours_end: string | null
  max_per_day: number
  enabled_types: string[]
}

export interface NotificationHistoryItem {
  id: string
  channel: string
  notification_type: string
  status: string
  sent_at: string | null
  payload: {
    subject: string
    event_title: string | null
  }
}

export interface ArtistPreference {
  id: number
  artist_name: string
  musicbrainz_id: string | null
  mb_genres: string[] | null
  genre_context: string
  weight: number
}

export interface AddArtistRequest {
  artist_name: string
  musicbrainz_id?: string
  mb_genres?: string[]
  genre_context: string
}

export interface MusicBrainzArtist {
  id: string
  name: string
  tags?: { name: string; count: number }[]
  country?: string
}

export interface DiscoveredSource {
  name: string
  url: string
  source_type: string
  description: string
  city: string
  state: string | null
  likely_categories: string[] | null
  has_ical_feed: boolean
  has_api: boolean
}

export const api = {
  // Events
  searchEvents(params: Record<string, string>): Promise<EventListResponse> {
    const query = new URLSearchParams(params).toString()
    return request(`/events?${query}`)
  },

  getEvent(id: string): Promise<Event> {
    return request(`/events/${id}`)
  },

  getTonightEvents(city: string): Promise<Event[]> {
    return request(`/events/tonight?city=${encodeURIComponent(city)}`)
  },

  // Auth
  register(data: { email: string; password: string; display_name: string; home_city?: string }): Promise<TokenResponse> {
    return request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  login(email: string, password: string): Promise<TokenResponse> {
    return request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
  },

  // Recommendations
  getRecommendations(params?: Record<string, string>): Promise<RecommendedEvent[]> {
    const query = params ? `?${new URLSearchParams(params).toString()}` : ''
    return request(`/recommendations${query}`)
  },

  // Preferences
  getPreferences(): Promise<PreferencesResponse> {
    return request('/me/preferences')
  },

  updatePreferences(updates: { category_slug: string; weight: number }[]): Promise<void> {
    return request('/me/preferences', {
      method: 'PUT',
      body: JSON.stringify(updates),
    })
  },

  updateDistancePreference(miles: number): Promise<void> {
    return request('/me/preferences/distance', {
      method: 'PUT',
      body: JSON.stringify(miles),
      headers: { 'Content-Type': 'application/json' },
    })
  },

  // Interactions
  saveEvent(eventId: string): Promise<void> {
    return request(`/me/events/${eventId}/save`, { method: 'POST' })
  },

  unsaveEvent(eventId: string): Promise<void> {
    return request(`/me/events/${eventId}/save`, { method: 'DELETE' })
  },

  logInteraction(eventId: string, interactionType: string): Promise<void> {
    return request(`/me/events/${eventId}/interact`, {
      method: 'POST',
      body: JSON.stringify({ interaction_type: interactionType }),
    })
  },

  getSavedEvents(): Promise<{ event_id: string; notes: string | null; created_at: string }[]> {
    return request('/me/saved-events')
  },

  // Categories
  getCategories(): Promise<CategoryInfo[]> {
    return request('/categories')
  },

  // Sources
  getSources(city?: string): Promise<EventSourceInfo[]> {
    const query = city ? `?city=${encodeURIComponent(city)}` : ''
    return request(`/sources${query}`)
  },

  discoverSources(city: string, state?: string): Promise<DiscoveredSource[]> {
    const params = new URLSearchParams({ city })
    if (state) params.set('state', state)
    return request(`/sources/discover?${params}`)
  },

  getSourcePreferences(): Promise<UserSourcePref[]> {
    return request('/sources/me/preferences')
  },

  updateSourcePreference(sourceId: number, preference: string): Promise<void> {
    return request('/sources/me/preferences', {
      method: 'PUT',
      body: JSON.stringify({ source_id: sourceId, preference }),
    })
  },

  // Notifications
  getNotificationChannels(): Promise<NotificationChannel[]> {
    return request('/me/notifications/channels')
  },

  addNotificationChannel(channelType: string, channelAddress: string): Promise<NotificationChannel> {
    return request('/me/notifications/channels', {
      method: 'POST',
      body: JSON.stringify({ channel_type: channelType, channel_address: channelAddress }),
    })
  },

  toggleNotificationChannel(channelId: string): Promise<{ id: string; is_active: boolean }> {
    return request(`/me/notifications/channels/${channelId}/toggle`, { method: 'PUT' })
  },

  removeNotificationChannel(channelId: string): Promise<void> {
    return request(`/me/notifications/channels/${channelId}`, { method: 'DELETE' })
  },

  getNotificationPreferences(): Promise<NotificationPrefs> {
    return request('/me/notifications/preferences')
  },

  updateNotificationPreferences(prefs: Partial<NotificationPrefs>): Promise<NotificationPrefs> {
    return request('/me/notifications/preferences', {
      method: 'PUT',
      body: JSON.stringify(prefs),
    })
  },

  getNotificationHistory(limit?: number): Promise<NotificationHistoryItem[]> {
    const query = limit ? `?limit=${limit}` : ''
    return request(`/me/notifications/history${query}`)
  },

  // AI / Trip Planning
  explainRecommendation(eventId: string): Promise<{
    event_id: string
    event_title: string
    explanation: string
    score: number
    score_breakdown: { category_affinity: number; embedding_similarity: number; popularity: number; distance_penalty: number }
  }> {
    return request(`/recommendations/explain/${eventId}`)
  },

  exploreTrip(data: {
    city: string
    date_from: string
    date_to: string
    interests?: string[]
  }): Promise<{
    city: string
    dates: string
    plan: string
    events: Array<{
      id: string
      title: string
      description: string | null
      venue_name: string | null
      city: string | null
      starts_at: string | null
      price_min: number | null
      price_max: number | null
      url: string | null
      image_url: string | null
      score: number
      categories: string[]
    }>
    total_events: number
  }> {
    return request('/trips/explore', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  // City ingestion
  ingestCity(city: string): Promise<{ status: string; city: string }> {
    return request('/ingest/city', {
      method: 'POST',
      body: JSON.stringify({ city }),
    })
  },

  // Artist preferences
  getArtists(): Promise<ArtistPreference[]> {
    return request('/me/artists')
  },

  addArtist(data: AddArtistRequest): Promise<ArtistPreference> {
    return request('/me/artists', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  removeArtist(artistName: string): Promise<void> {
    return request(`/me/artists/${encodeURIComponent(artistName)}`, { method: 'DELETE' })
  },

  updateHomeCity(city: string): Promise<{ home_city: string }> {
    return request('/me/city', {
      method: 'PUT',
      body: JSON.stringify({ city }),
    })
  },

  // MusicBrainz artist search (public API, called directly from frontend)
  async searchMusicBrainzArtists(query: string): Promise<MusicBrainzArtist[]> {
    const resp = await fetch(
      `https://musicbrainz.org/ws/2/artist?query=${encodeURIComponent(query)}&fmt=json&limit=5`,
      { headers: { 'User-Agent': 'BubbaRooEvents/0.1 (dev)' } }
    )
    if (!resp.ok) return []
    const data = await resp.json()
    return data.artists ?? []
  },
}
