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
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "think": False,
                    "options": {"num_predict": max_tokens},
                },
            )

        if response.status_code == 404:
            raise RuntimeError(f"Ollama model not found: {self._model}")
        if response.status_code != 200:
            raise RuntimeError(f"Ollama error {response.status_code}: {response.text}")

        msg = response.json()["message"]
        return msg.get("content") or msg.get("thinking", "")
