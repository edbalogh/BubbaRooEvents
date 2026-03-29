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
