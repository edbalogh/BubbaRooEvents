# BubbaRoo Events

A local events discovery and recommendation platform that scans for events, learns your preferences, and proactively notifies you of things you'll love.

## Features

- **Event Discovery**: Search and browse local events by city, category, date, and price
- **Smart Recommendations**: AI-powered personalization that learns from your interactions
- **Multi-Channel Notifications**: Get notified via email, SMS, Slack, or push notifications
- **Trip Planning**: Find events in cities you're visiting
- **Tonight View**: Quick access to what's happening right now

## Tech Stack

- **Backend**: FastAPI (Python 3.12+), SQLAlchemy, Celery
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS
- **Database**: PostgreSQL 16 + pgvector
- **Cache/Queue**: Redis
- **AI**: Claude API + sentence-transformers

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for frontend development)
- Python 3.12+ (for backend development)

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env with your API keys (optional - mock data works without them)
```

### 2. Start services

```bash
docker compose up -d db redis
```

### 3. Run backend

```bash
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

### 4. Seed mock data

```bash
curl -X POST http://localhost:8000/api/v1/seed?city=Austin
```

### 5. Run frontend

```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:5173

## API Docs

Once the backend is running, visit http://localhost:8000/docs for the interactive Swagger UI.

## Project Structure

```
backend/
  app/
    api/v1/          # Route handlers
    core/            # Config, database, auth
    models/          # SQLAlchemy ORM models
    schemas/         # Pydantic request/response schemas
    services/        # Business logic
    ingestion/       # Event source adapters (Ticketmaster, etc.)
    notifications/   # Notification channel adapters
  worker/            # Celery tasks for ingestion & notifications
frontend/
  src/
    api/             # API client
    components/      # React components
    pages/           # Route pages
    context/         # React context providers
```

## Data Sources

- **Ticketmaster Discovery API** (primary) - 5,000 calls/day free
- **SeatGeek Platform API** (Phase 4) - generous free tier
- **Mock Data** - 10 sample events for development

## License

MIT
