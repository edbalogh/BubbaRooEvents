# Ollama LLM Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace direct Anthropic API calls with a local Ollama provider abstraction, using `qwen3.5:9b` for recommendation explanations and `gpt-oss:latest` for trip planning, failing loudly on any error.

**Architecture:** A new `LLMProvider` ABC and `OllamaProvider` concrete class live in `llm_provider.py`. `ai_service.py` instantiates two `OllamaProvider` objects (one per model) and delegates all HTTP to them. All error-swallowing fallback logic is removed.

**Tech Stack:** Python 3.12, httpx (already a dependency), pytest + pytest-asyncio, Ollama REST API (`/api/chat`)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/app/services/llm_provider.py` | Create | `LLMProvider` ABC + `OllamaProvider` implementation |
| `backend/app/services/ai_service.py` | Modify | Use providers instead of `_call_claude()`; remove fallbacks |
| `backend/app/core/config.py` | Modify | Swap `anthropic_api_key` for three Ollama settings |
| `.env` | Modify | Replace `ANTHROPIC_API_KEY` with Ollama vars |
| `.env.example` | Modify | Same |
| `backend/tests/services/test_llm_provider.py` | Create | Unit tests for `OllamaProvider` |
| `backend/tests/services/test_ai_service.py` | Create | Unit tests for `explain_recommendation` and `plan_trip` |

---

### Task 1: Add Ollama settings to config

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/__init__.py` (empty) and `backend/tests/services/__init__.py` (empty), then create `backend/tests/services/test_llm_provider.py`:

```python
import pytest
from app.core.config import Settings


def test_ollama_settings_have_defaults():
    s = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://x:x@localhost/x",
        database_url_sync="postgresql://x:x@localhost/x",
    )
    assert s.ollama_base_url == "http://localhost:11434"
    assert s.ollama_recommend_model == "qwen3.5:9b"
    assert s.ollama_trip_model == "gpt-oss:latest"


def test_anthropic_key_is_gone():
    s = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://x:x@localhost/x",
        database_url_sync="postgresql://x:x@localhost/x",
    )
    assert not hasattr(s, "anthropic_api_key")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/services/test_llm_provider.py::test_ollama_settings_have_defaults -v
```

Expected: `FAILED` — `Settings` has no `ollama_base_url` attribute.

- [ ] **Step 3: Update config.py**

Replace the `# AI (Claude API)` block in `backend/app/core/config.py`:

```python
    # AI (Ollama)
    ollama_base_url: str = "http://localhost:11434"
    ollama_recommend_model: str = "qwen3.5:9b"
    ollama_trip_model: str = "gpt-oss:latest"
```

Remove the line:
```python
    anthropic_api_key: str = ""
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/services/test_llm_provider.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/config.py backend/tests/__init__.py backend/tests/services/__init__.py backend/tests/services/test_llm_provider.py
git commit -m "feat: add Ollama config settings, remove Anthropic key"
```

---

### Task 2: Create LLMProvider ABC and OllamaProvider

**Files:**
- Create: `backend/app/services/llm_provider.py`
- Modify: `backend/tests/services/test_llm_provider.py`

- [ ] **Step 1: Write failing tests for OllamaProvider**

Add to `backend/tests/services/test_llm_provider.py`:

```python
import pytest
import httpx
import respx
from app.services.llm_provider import OllamaProvider


@respx.mock
@pytest.mark.asyncio
async def test_ollama_provider_returns_text():
    respx.post("http://localhost:11434/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={"message": {"content": "This is a great event for you!"}},
        )
    )
    provider = OllamaProvider(base_url="http://localhost:11434", model="qwen3.5:9b")
    result = await provider.complete(
        system="You are a helpful assistant.",
        user="Why is this event good?",
        max_tokens=500,
    )
    assert result == "This is a great event for you!"


@respx.mock
@pytest.mark.asyncio
async def test_ollama_provider_raises_on_model_not_found():
    respx.post("http://localhost:11434/api/chat").mock(
        return_value=httpx.Response(404, text="model not found")
    )
    provider = OllamaProvider(base_url="http://localhost:11434", model="bad-model")
    with pytest.raises(RuntimeError, match="Ollama model not found: bad-model"):
        await provider.complete(system="sys", user="user", max_tokens=100)


@respx.mock
@pytest.mark.asyncio
async def test_ollama_provider_raises_on_non_200():
    respx.post("http://localhost:11434/api/chat").mock(
        return_value=httpx.Response(500, text="internal error")
    )
    provider = OllamaProvider(base_url="http://localhost:11434", model="qwen3.5:9b")
    with pytest.raises(RuntimeError, match="Ollama error 500"):
        await provider.complete(system="sys", user="user", max_tokens=100)


@pytest.mark.asyncio
async def test_ollama_provider_raises_on_connection_error():
    provider = OllamaProvider(base_url="http://localhost:19999", model="qwen3.5:9b")
    with pytest.raises(httpx.ConnectError):
        await provider.complete(system="sys", user="user", max_tokens=100)
```

- [ ] **Step 2: Install respx for mocking httpx**

Add `respx>=0.21.0` to dev dependencies in `backend/pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "httpx>=0.27.0",
    "respx>=0.21.0",
    "ruff>=0.5.0",
]
```

Then install:
```bash
cd backend && pip install -e ".[dev]"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/services/test_llm_provider.py -k "ollama_provider" -v
```

Expected: `ERROR` — `cannot import name 'OllamaProvider'`

- [ ] **Step 4: Create llm_provider.py**

Create `backend/app/services/llm_provider.py`:

```python
"""LLM provider abstraction for pluggable AI backends."""

from abc import ABC, abstractmethod

import httpx


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str, max_tokens: int) -> str:
        """Send a prompt and return the response text. Raises on any failure."""


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def complete(self, system: str, user: str, max_tokens: int) -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
            )

        if response.status_code == 404:
            raise RuntimeError(f"Ollama model not found: {self._model}")
        if response.status_code != 200:
            raise RuntimeError(f"Ollama error {response.status_code}: {response.text}")

        return response.json()["message"]["content"]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/services/test_llm_provider.py -v
```

Expected: `6 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/llm_provider.py backend/tests/services/test_llm_provider.py backend/pyproject.toml
git commit -m "feat: add OllamaProvider with LLMProvider ABC"
```

---

### Task 3: Update ai_service.py to use providers

**Files:**
- Modify: `backend/app/services/ai_service.py`
- Create: `backend/tests/services/test_ai_service.py`

- [ ] **Step 1: Write failing tests for ai_service**

Create `backend/tests/services/test_ai_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_explain_recommendation_returns_provider_text():
    mock_provider = AsyncMock()
    mock_provider.complete.return_value = "You'll love this jazz event!"

    with patch("app.services.ai_service._recommend_provider", mock_provider):
        from app.services.ai_service import explain_recommendation
        result = await explain_recommendation(
            event_title="Jazz Night",
            event_description="A smooth evening of jazz",
            event_categories=["music", "jazz"],
            event_venue="Blue Note",
            event_city="Austin",
            event_date="2026-04-01",
            event_price_min=20.0,
            score=0.85,
            score_breakdown={"category_affinity": 0.9, "embedding_similarity": 0.7, "popularity": 0.5},
            user_top_categories=["music", "concerts"],
        )

    assert result == "You'll love this jazz event!"
    mock_provider.complete.assert_called_once()


@pytest.mark.asyncio
async def test_explain_recommendation_propagates_error():
    mock_provider = AsyncMock()
    mock_provider.complete.side_effect = RuntimeError("Ollama model not found: qwen3.5:9b")

    with patch("app.services.ai_service._recommend_provider", mock_provider):
        from app.services.ai_service import explain_recommendation
        with pytest.raises(RuntimeError, match="Ollama model not found"):
            await explain_recommendation(
                event_title="Jazz Night",
                event_description=None,
                event_categories=[],
                event_venue=None,
                event_city=None,
                event_date=None,
                event_price_min=None,
                score=0.5,
                score_breakdown={},
                user_top_categories=[],
            )


@pytest.mark.asyncio
async def test_plan_trip_returns_provider_text():
    mock_provider = AsyncMock()
    mock_provider.complete.return_value = "Day 1: Start with the jazz festival..."

    with patch("app.services.ai_service._trip_provider", mock_provider):
        from app.services.ai_service import plan_trip
        result = await plan_trip(
            destination_city="Austin",
            travel_dates="April 1-3",
            interests=["music", "food"],
            events_context=[{"title": "Jazz Fest", "date": "2026-04-01", "venue": "Stubb's", "price_min": 30}],
        )

    assert result == "Day 1: Start with the jazz festival..."
    mock_provider.complete.assert_called_once()


@pytest.mark.asyncio
async def test_plan_trip_propagates_error():
    mock_provider = AsyncMock()
    mock_provider.complete.side_effect = RuntimeError("Ollama error 500: internal error")

    with patch("app.services.ai_service._trip_provider", mock_provider):
        from app.services.ai_service import plan_trip
        with pytest.raises(RuntimeError, match="Ollama error 500"):
            await plan_trip(
                destination_city="Austin",
                travel_dates="April 1-3",
                interests=[],
                events_context=[],
            )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/services/test_ai_service.py -v
```

Expected: `FAILED` — `cannot import name '_recommend_provider'` (module-level attribute doesn't exist yet)

- [ ] **Step 3: Rewrite ai_service.py**

Replace the entire contents of `backend/app/services/ai_service.py`:

```python
"""AI-powered services using local Ollama models.

Provides recommendation explanations and trip planning through
natural language generation. Errors propagate — no silent fallbacks.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.llm_provider import OllamaProvider

_recommend_provider = OllamaProvider(
    base_url=settings.ollama_base_url,
    model=settings.ollama_recommend_model,
)

_trip_provider = OllamaProvider(
    base_url=settings.ollama_base_url,
    model=settings.ollama_trip_model,
)


async def explain_recommendation(
    event_title: str,
    event_description: str | None,
    event_categories: list[str],
    event_venue: str | None,
    event_city: str | None,
    event_date: str | None,
    event_price_min: float | None,
    score: float,
    score_breakdown: dict,
    user_top_categories: list[str],
) -> str:
    """Generate a natural language explanation of why an event was recommended."""
    system_prompt = (
        "You are a friendly events concierge for BubbaRoo Events. "
        "Explain in 2-3 sentences why this event is a great match for the user. "
        "Be enthusiastic but genuine. Reference specific details about the event "
        "and the user's interests. Don't mention scores or numbers."
    )

    user_message = f"""Event: {event_title}
Description: {event_description or 'N/A'}
Categories: {', '.join(event_categories) if event_categories else 'General'}
Venue: {event_venue or 'TBD'}
City: {event_city or 'N/A'}
Date: {event_date or 'TBD'}
Price: {'Free' if event_price_min == 0 else f'${event_price_min}+' if event_price_min else 'TBD'}

User's favorite categories: {', '.join(user_top_categories) if user_top_categories else 'Still learning'}

Match signals:
- Category match strength: {score_breakdown.get('category_affinity', 0):.0%}
- Taste similarity: {score_breakdown.get('embedding_similarity', 0):.0%}
- Popularity: {score_breakdown.get('popularity', 0):.0%}
- Overall match: {score:.0%}

Explain why this event is a great fit for this user."""

    return await _recommend_provider.complete(system_prompt, user_message, max_tokens=500)


async def plan_trip(
    destination_city: str,
    travel_dates: str,
    interests: list[str],
    events_context: list[dict],
) -> str:
    """Generate an AI-powered trip plan based on available events."""
    system_prompt = (
        "You are a friendly trip planning assistant for BubbaRoo Events. "
        "Help users plan an amazing trip by suggesting which events to attend "
        "and how to structure their time. Be specific about event details. "
        "Suggest a rough itinerary if multiple days. Keep it concise and fun. "
        "Use the events provided - don't make up events that aren't in the list."
    )

    events_text = ""
    for i, e in enumerate(events_context[:15], 1):
        price = "Free" if e.get("price_min") == 0 else f"${e.get('price_min', '?')}+" if e.get("price_min") else "TBD"
        events_text += (
            f"{i}. {e['title']}\n"
            f"   Date: {e.get('date', 'TBD')} | Venue: {e.get('venue', 'TBD')} | Price: {price}\n"
            f"   {e.get('description', '')[:150]}\n\n"
        )

    user_message = f"""I'm planning a trip to {destination_city} during {travel_dates}.

My interests: {', '.join(interests) if interests else 'Open to anything!'}

Here are the events happening during my trip:

{events_text if events_text else 'No events found for these dates yet.'}

Please suggest which events I should attend and help me plan my time there."""

    return await _trip_provider.complete(system_prompt, user_message, max_tokens=1000)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/services/test_ai_service.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Run all tests**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: `10 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai_service.py backend/tests/services/test_ai_service.py
git commit -m "feat: wire ai_service to OllamaProvider, remove Anthropic fallbacks"
```

---

### Task 4: Update env files

**Files:**
- Modify: `.env`
- Modify: `.env.example`

- [ ] **Step 1: Update .env.example**

Replace the `# Claude API` block in `.env.example`:

```bash
# Ollama (local AI)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_RECOMMEND_MODEL=qwen3.5:9b
OLLAMA_TRIP_MODEL=gpt-oss:latest
```

Remove:
```bash
# Claude API
ANTHROPIC_API_KEY=your-anthropic-api-key
```

- [ ] **Step 2: Update .env**

Make the same change in `.env` — replace:
```
ANTHROPIC_API_KEY=your-anthropic-api-key
```
With:
```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_RECOMMEND_MODEL=qwen3.5:9b
OLLAMA_TRIP_MODEL=gpt-oss:latest
```

- [ ] **Step 3: Restart api container to pick up new env**

```bash
docker compose restart api
```

- [ ] **Step 4: Verify api starts cleanly**

```bash
docker compose logs api --tail=10
```

Expected: `Application startup complete.` with no errors.

- [ ] **Step 5: Commit**

```bash
git add .env.example
git commit -m "feat: swap ANTHROPIC_API_KEY for Ollama env vars"
```

Note: `.env` is gitignored — do not commit it.

---

### Task 5: Smoke test end-to-end

- [ ] **Step 1: Ensure Ollama is running**

```bash
ollama list
```

Expected: shows `qwen3.5:9b` and `gpt-oss:latest` in the list.

- [ ] **Step 2: Test recommendation explanation endpoint**

First register a user and get a token:
```bash
curl -s -X POST "http://localhost:8001/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test1234","display_name":"Tester"}' | python3 -m json.tool
```

Then login:
```bash
curl -s -X POST "http://localhost:8001/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test1234"}' | python3 -m json.tool
```

Copy the `access_token` from the response.

- [ ] **Step 3: Get a recommendation explanation**

Replace `<TOKEN>` and `<EVENT_ID>` with values from the seed data:

```bash
# Get a list of events first
curl -s "http://localhost:8001/api/v1/events?city=Austin" | python3 -m json.tool | head -40
```

```bash
# Then call the explain endpoint
curl -s "http://localhost:8001/api/v1/recommendations/explain/<EVENT_ID>" \
  -H "Authorization: Bearer <TOKEN>" | python3 -m json.tool
```

Expected: response contains an `explanation` field with natural language text from `qwen3.5:9b`.

- [ ] **Step 4: Test trip planner endpoint**

```bash
curl -s -X POST "http://localhost:8001/api/v1/trips/explore" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"city":"Austin","date_from":"2026-04-01","date_to":"2026-04-03","interests":["music","food"]}' \
  | python3 -m json.tool
```

Expected: response contains an `ai_plan` field with trip itinerary text from `gpt-oss:latest`.

- [ ] **Step 5: Final commit**

```bash
git add -p  # review any remaining changes
git commit -m "feat: complete Ollama provider integration"
git push
```
