from __future__ import annotations

import json
import os
from typing import TypeVar

from anthropic import Anthropic
from pydantic import BaseModel, ValidationError

from .llm import PromptMessage, StructuredLLM


T = TypeVar("T", bound=BaseModel)


class ClaudeStructuredLLM(StructuredLLM):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        resolved_api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not resolved_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")

        self.client = Anthropic(api_key=resolved_api_key)
        self.model = model or os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")

    def generate_structured(
        self,
        *,
        messages: list[PromptMessage],
        response_model: type[T],
    ) -> T:
        """Generate structured output matching the response_model schema."""
        system_messages = [message.content for message in messages if message.role == "system"]
        non_system_messages = [message for message in messages if message.role != "system"]

        if not non_system_messages:
            raise RuntimeError("At least one non-system message is required.")

        # Build the system prompt with schema instructions
        system_prompt = "\n\n".join(system_messages) if system_messages else ""
        schema = response_model.model_json_schema()
        schema_prompt = f"""You must respond with valid JSON matching this schema:

{json.dumps(schema, indent=2)}

Respond ONLY with the JSON object, no additional text."""

        if system_prompt:
            system_prompt += f"\n\n{schema_prompt}"
        else:
            system_prompt = schema_prompt

        # Convert messages to Claude format
        claude_messages = [
            {
                "role": message.role if message.role in ["user", "assistant"] else "user",
                "content": message.content,
            }
            for message in non_system_messages
        ]

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=claude_messages,
        )

        if not response.content or not response.content[0].text:
            raise RuntimeError("Claude returned an empty response.")

        response_text = response.content[0].text

        # Extract JSON from response (handle cases where Claude wraps it in markdown)
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        try:
            return response_model.model_validate_json(response_text)
        except ValidationError as exc:
            preview = response_text[:800]
            raise RuntimeError(
                "Claude returned invalid structured JSON. "
                "This usually means the model output did not match the schema.\n"
                f"Validation error: {exc}\n"
                f"Response preview:\n{preview}"
            ) from exc

    def generate_text(
        self,
        *,
        messages: list[PromptMessage],
    ) -> str:
        """Generate free-form text (not structured JSON)."""
        system_messages = [message.content for message in messages if message.role == "system"]
        non_system_messages = [message for message in messages if message.role != "system"]

        if not non_system_messages:
            raise RuntimeError("At least one non-system message is required.")

        system_prompt = "\n\n".join(system_messages) if system_messages else None

        claude_messages = [
            {
                "role": message.role if message.role in ["user", "assistant"] else "user",
                "content": message.content,
            }
            for message in non_system_messages
        ]

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=claude_messages,
        )

        if not response.content or not response.content[0].text:
            raise RuntimeError("Claude returned an empty response.")

        return response.content[0].text
