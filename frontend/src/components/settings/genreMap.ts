export interface GenreEntry {
  label: string
  slugs: string[]        // maps to existing category slugs in DB
  subGenreSlugs?: string[] // optional deeper slugs shown in step 3
}

export interface EventTypeEntry {
  label: string
  emoji: string
  genres: GenreEntry[]
}

export const EVENT_TYPE_MAP: EventTypeEntry[] = [
  {
    label: 'Music',
    emoji: '🎵',
    genres: [
      { label: 'Rock', slugs: ['rock', 'indie-rock', 'alternative-rock', 'classic-rock'], subGenreSlugs: ['indie-rock', 'alternative', 'hard-rock', 'punk', 'metal', 'southern-rock', 'folk-rock', 'roots-rock'] },
      { label: 'Pop', slugs: ['pop', 'indie-pop', 'dance-pop', 'synth-pop', 'electro-pop'], subGenreSlugs: ['indie-pop', 'dance-pop', 'synth-pop', 'electro-pop', 'pop-rock'] },
      { label: 'Hip-Hop / Rap', slugs: ['hip-hop/rap', 'trap'], subGenreSlugs: ['trap'] },
      { label: 'Country', slugs: ['country', 'country-folk', 'classic-country', 'contemporary-country', 'americana', 'honky-tonk'], subGenreSlugs: ['country-folk', 'classic-country', 'contemporary-country', 'americana', 'honky-tonk', 'old-time-country', 'alternative-country'] },
      { label: 'Jazz', slugs: ['jazz', 'jazz-blues', 'soul-jazz', 'avant-garde-jazz'], subGenreSlugs: ['jazz-blues', 'soul-jazz', 'avant-garde-jazz'] },
      { label: 'Electronic / Dance', slugs: ['dance/electronic', 'house', 'dj', 'club-dance', 'electro-techno'], subGenreSlugs: ['house', 'dj', 'club-dance', 'electro-techno', 'ambient'] },
      { label: 'Classical', slugs: ['classical', 'classical/vocal', 'ballet'], subGenreSlugs: ['classical/vocal'] },
      { label: 'R&B / Soul', slugs: ['r&b', 'soul', 'funk'], subGenreSlugs: ['funk'] },
      { label: 'Folk / Americana', slugs: ['folk', 'americana', 'singer-songwriter', 'indie-folk', 'country-folk', 'alternative-folk'], subGenreSlugs: ['singer-songwriter', 'indie-folk', 'alternative-folk', 'folk-rock'] },
      { label: 'Metal', slugs: ['metal', 'heavy-metal', 'hard-rock', 'death-metal/black-metal', 'nu-metal'], subGenreSlugs: ['heavy-metal', 'hard-rock', 'death-metal/black-metal', 'nu-metal', 'sludge-metal'] },
      { label: 'Blues', slugs: ['blues', 'jazz-blues'], subGenreSlugs: ['jazz-blues'] },
      { label: 'Latin', slugs: ['latin'], subGenreSlugs: [] },
    ],
  },
  {
    label: 'Sports',
    emoji: '🏟',
    genres: [
      { label: 'Football', slugs: ['football'] },
      { label: 'Basketball', slugs: ['basketball', 'nba'] },
      { label: 'Baseball', slugs: ['baseball', 'mlb'] },
      { label: 'Soccer', slugs: ['soccer', 'mls'] },
      { label: 'Hockey', slugs: ['hockey', 'nhl'] },
      { label: 'Motorsports', slugs: ['motorsports/racing'] },
      { label: 'Other Sports', slugs: ['sports', 'minor-league'] },
    ],
  },
  {
    label: 'Arts & Theatre',
    emoji: '🎭',
    genres: [
      { label: 'Theatre', slugs: ['theatre', 'musical', 'miscellaneous-theatre'] },
      { label: 'Ballet & Dance', slugs: ['ballet', 'dance'] },
      { label: 'Arts & Exhibitions', slugs: ['arts'] },
      { label: 'Comedy', slugs: ['comedy'] },
    ],
  },
  {
    label: 'Food & Drink',
    emoji: '🍔',
    genres: [
      { label: 'Food Festivals', slugs: ['food', 'food-&-drink', 'fairs-&-festivals'] },
      { label: 'Restaurants & Markets', slugs: ['restaurant', 'market'] },
    ],
  },
  {
    label: 'Technology',
    emoji: '💻',
    genres: [
      { label: 'Tech Conferences', slugs: ['technology', 'conference', 'expo'] },
      { label: 'Meetups', slugs: ['meetup'] },
    ],
  },
  {
    label: 'Wellness',
    emoji: '🧘',
    genres: [
      { label: 'Fitness', slugs: ['fitness', 'wellness'] },
      { label: 'Outdoor', slugs: ['outdoor'] },
    ],
  },
  {
    label: 'Family',
    emoji: '👨‍👩‍👧',
    genres: [
      { label: 'Kids Events', slugs: ['kids', 'family'] },
    ],
  },
  {
    label: 'Nightlife',
    emoji: '🌙',
    genres: [
      { label: 'Clubs & DJ', slugs: ['nightlife', 'dj', 'club-dance'] },
    ],
  },
]

// All slugs that belong to a given top-level type
export function slugsForType(type: EventTypeEntry): string[] {
  return type.genres.flatMap((g) => g.slugs)
}
