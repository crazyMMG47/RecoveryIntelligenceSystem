from __future__ import annotations

import json
from typing import TypeVar

import requests
from pydantic import BaseModel, ValidationError

from .llm import PromptMessage, StructuredLLM

T = TypeVar("T", bound=BaseModel)


class OllamaStructuredLLM(StructuredLLM):
    """Ollama backend that satisfies the StructuredLLM protocol.

    Uses /api/chat with JSON-schema-constrained output so the model returns
    a JSON object that matches the requested Pydantic response_model.

    Requires Ollama >= 0.3.0 (json schema format support).
    Run: ollama serve
    """

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
        timeout: int = 120,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate_structured(
        self,
        *,
        messages: list[PromptMessage],
        response_model: type[T],
    ) -> T:
        chat_messages = [
            {"role": msg.role if msg.role != "model" else "assistant", "content": msg.content}
            for msg in messages
        ]

        payload = {
            "model": self.model,
            "messages": chat_messages,
            "stream": False,
            "format": response_model.model_json_schema(),
            "options": {
                "temperature": 0.1,
                "num_ctx": 8192,
            },
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Ollama request failed. Is `ollama serve` running at {self.base_url}?\n{exc}"
            ) from exc

        data = response.json()
        raw = data.get("message", {}).get("content", "")

        if not raw:
            raise RuntimeError(f"Ollama returned an empty response. Full payload: {data}")

        try:
            return response_model.model_validate_json(raw)
        except ValidationError as exc:
            preview = raw[:800]
            raise RuntimeError(
                f"Ollama returned invalid structured JSON for {response_model.__name__}.\n"
                f"Validation error: {exc}\n"
                f"Response preview:\n{preview}"
            ) from exc
