import httpx
import pytest
import respx
from app.core.config import Settings
from app.services.llm_provider import OllamaProvider


def test_ollama_settings_have_defaults():
    s = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://x:x@localhost/x",
        database_url_sync="postgresql://x:x@localhost/x",
    )
    assert s.ollama_base_url == "http://localhost:11434"
    assert s.ollama_recommend_model == "gemma4:26b"
    assert s.ollama_trip_model == "gemma4:26b"


def test_anthropic_key_is_gone():
    s = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://x:x@localhost/x",
        database_url_sync="postgresql://x:x@localhost/x",
    )
    assert not hasattr(s, "anthropic_api_key")


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
