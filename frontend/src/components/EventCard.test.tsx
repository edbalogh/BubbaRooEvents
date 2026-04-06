import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import EventCard from './EventCard'
import type { Event } from '../api/client'

const baseEvent: Event = {
  id: '1',
  source: 'ticketmaster',
  title: 'Jazz in the Park',
  description: null,
  venue_name: 'Zilker Park',
  venue_address: null,
  city: 'Austin',
  state: 'TX',
  country: 'US',
  latitude: null,
  longitude: null,
  starts_at: '2026-04-12T19:00:00Z',
  ends_at: null,
  on_sale_at: null,
  price_min: null,
  price_max: null,
  currency: 'USD',
  url: null,
  image_url: null,
  status: 'active',
  categories: [],
}

function renderCard(event: Partial<Event> = {}) {
  return render(
    <MemoryRouter>
      <EventCard event={{ ...baseEvent, ...event }} />
    </MemoryRouter>
  )
}

describe('EventCard source display', () => {
  it('shows display name for known source slug', () => {
    renderCard({ source: 'ticketmaster' })
    expect(screen.getByText('Ticketmaster')).toBeInTheDocument()
  })

  it('shows display name for eventbrite', () => {
    renderCard({ source: 'eventbrite' })
    expect(screen.getByText('Eventbrite')).toBeInTheDocument()
  })

  it('title-cases unknown slugs', () => {
    renderCard({ source: 'my-local-venue' })
    expect(screen.getByText('My Local Venue')).toBeInTheDocument()
  })

  it('title-cases single-word unknown slugs', () => {
    renderCard({ source: 'unknown' })
    expect(screen.getByText('Unknown')).toBeInTheDocument()
  })
})
