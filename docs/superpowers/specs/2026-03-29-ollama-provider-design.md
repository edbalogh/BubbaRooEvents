# Ollama LLM Provider Design

**Date:** 2026-03-29
**Status:** Approved

## Summary

Replace the Anthropic Claude API with a local Ollama instance. Introduce a thin `LLMProvider` abstraction so the routing logic lives in one place, and fail loudly if Ollama is unavailable.

## Context

The app currently calls the Anthropic REST API directly via `httpx` in two places:
- `explain_recommendation()` — generates a 2-3 sentence explanation for why an event matches a user
- `plan_trip()` — generates a natural language trip itinerary from a list of events

Both calls are in `backend/app/services/ai_service.py`. There is no SDK dependency — just raw HTTP. The existing fallback logic (swallow errors, return `None`, use templates) is removed. Errors propagate as HTTP 503/504.

## Architecture

### New file: `backend/app/services/llm_provider.py`

```
LLMProvider (abstract base class)
  └── OllamaProvider
        - accepts model name at construction
        - async def complete(system: str, user: str, max_tokens: int) -> str
        - raises on any failure (no swallowing)
```

`ai_service.py` instantiates two `OllamaProvider` objects at module level:
- `_recommend_provider = OllamaProvider(model=settings.ollama_recommend_model)`
- `_trip_provider = OllamaProvider(model=settings.ollama_trip_model)`

No other files change their public interfaces.

## Data Flow

```
API endpoint
  → ai_service.explain_recommendation() / plan_trip()
  → OllamaProvider.complete(system, user, max_tokens)
  → POST http://{OLLAMA_BASE_URL}/api/chat
      body: { model, messages: [{role:system}, {role:user}], stream:false, options:{num_predict} }
  → returns response["message"]["content"]
```

## Configuration

Three new env vars replace `ANTHROPIC_API_KEY`:

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_RECOMMEND_MODEL` | `qwen3.5:9b` | Model for recommendation explanations |
| `OLLAMA_TRIP_MODEL` | `gpt-oss:latest` | Model for trip planning |

`ANTHROPIC_API_KEY` is removed from `.env`, `.env.example`, and `config.py`.

## Error Handling

Fail loudly — no fallbacks:

| Failure | Behavior |
|---|---|
| Ollama not running | `httpx.ConnectError` → FastAPI returns 503 |
| Model not found (404) | `RuntimeError("Ollama model not found: {model}")` → 500 |
| Timeout (30s) | `httpx.TimeoutException` → 504 |
| Non-200 response | `RuntimeError("Ollama error {status}: {body}")` → 500 |

The `try/except` blocks in `ai_service.py` that currently swallow errors and return `None` are removed entirely.

## Files Changed

| File | Change |
|---|---|
| `backend/app/services/llm_provider.py` | **New** — `LLMProvider` ABC + `OllamaProvider` |
| `backend/app/services/ai_service.py` | Replace `_call_claude()` with provider calls; remove error suppression |
| `backend/app/core/config.py` | Swap `anthropic_api_key` for three Ollama settings |
| `.env` | Replace `ANTHROPIC_API_KEY` with Ollama vars |
| `.env.example` | Same |

## Models in Use

| Model | Size | Used for |
|---|---|---|
| `qwen3.5:9b` | 6.6 GB | Recommendation explanations (max 500 tokens) |
| `gpt-oss:latest` | 13 GB | Trip planning (max 1000 tokens) |

Both are already installed locally via Ollama.

## Out of Scope

- Streaming responses
- Ollama model management (pull, delete)
- Switching providers via runtime config
- Sentence-transformer embeddings (already local, unchanged)
