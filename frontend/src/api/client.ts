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

  // Seed (dev only)
  seedData(city: string = 'Austin'): Promise<{ events_seeded: number }> {
    return request(`/seed?city=${encodeURIComponent(city)}`, { method: 'POST' })
  },
}
