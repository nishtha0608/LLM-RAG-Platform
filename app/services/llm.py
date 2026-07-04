"""LLM generation service. Provider is selected via `settings.llm_provider`
("anthropic" or "ollama") behind a small Protocol so callers never branch
on provider type.

Note: `stream_completion` is declared as a plain (non-async) method on the
Protocol because the implementations are async *generator* functions --
calling one returns an AsyncIterator synchronously, it is not awaited."""

import json
from collections.abc import AsyncIterator
from typing import Protocol, cast

import anthropic
import httpx
from anthropic.types import MessageParam
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings


class LLMNotConfiguredError(Exception):
    """Raised when the selected LLM provider is missing required configuration."""


class LLMProvider(Protocol):
    def stream_completion(
        self, system_prompt: str, history: list[dict[str, str]]
    ) -> AsyncIterator[str]: ...


class AnthropicLLMProvider:
    def __init__(self) -> None:
        settings = get_settings()
        if settings.anthropic_api_key is None:
            raise LLMNotConfiguredError(
                "ANTHROPIC_API_KEY is not set; configure it to use the anthropic LLM provider"
            )
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value()
        )
        self._model = settings.llm_model
        self._max_tokens = settings.llm_max_tokens
        self._temperature = settings.llm_temperature

    @retry(
        retry=retry_if_exception_type((anthropic.APIConnectionError, anthropic.RateLimitError)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def stream_completion(
        self, system_prompt: str, history: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        messages = cast(list[MessageParam], history)
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text


class OllamaLLMProvider:
    """Streams completions from a local Ollama server. No API key required,
    which makes it a sensible default for local development."""

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.ollama_base_url
        self._model = settings.ollama_model
        self._temperature = settings.llm_temperature
        self._num_ctx = settings.ollama_num_ctx
        self._num_predict = settings.ollama_num_predict

    @retry(
        retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def stream_completion(
        self, system_prompt: str, history: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        messages = [{"role": "system", "content": system_prompt}, *history]
        timeout = httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)
        async with (
            httpx.AsyncClient(base_url=self._base_url, timeout=timeout) as client,
            client.stream(
                "POST",
                "/api/chat",
                json={
                    "model": self._model,
                    "messages": messages,
                    "options": {
                        "temperature": self._temperature,
                        "num_ctx": self._num_ctx,
                        "num_predict": self._num_predict,
                    },
                    "stream": True,
                },
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "anthropic":
        return AnthropicLLMProvider()
    return OllamaLLMProvider()
