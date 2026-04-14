from __future__ import annotations

import os
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from .llm import PromptMessage, StructuredLLM


T = TypeVar("T", bound=BaseModel)


class GeminiStructuredLLM(StructuredLLM):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        resolved_api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not resolved_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set.")

        self.client = genai.Client(api_key=resolved_api_key)
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

    def generate_structured(
        self,
        *,
        messages: list[PromptMessage],
        response_model: type[T],
    ) -> T:
        system_messages = [message.content for message in messages if message.role == "system"]
        non_system_messages = [message for message in messages if message.role != "system"]

        if not non_system_messages:
            raise RuntimeError("At least one non-system message is required for Gemini generate_content.")

        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                types.Content(
                    role="user" if message.role != "model" else "model",
                    parts=[types.Part.from_text(text=message.content)],
                )
                for message in non_system_messages
            ],
            config=types.GenerateContentConfig(
                system_instruction="\n\n".join(system_messages) if system_messages else None,
                response_mime_type="application/json",
                response_json_schema=response_model.model_json_schema(),
            ),
        )

        if not response.text:
            raise RuntimeError("Gemini returned an empty response.")

        return response_model.model_validate_json(response.text)
