from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class PromptMessage:
    role: str
    content: str


class StructuredLLM(Protocol):
    def generate_structured(
        self,
        *,
        messages: list[PromptMessage],
        response_model: type[T],
    ) -> T: ...


class UnconfiguredStructuredLLM:
    def generate_structured(
        self,
        *,
        messages: list[PromptMessage],
        response_model: type[T],
    ) -> T:
        raise RuntimeError(
            "Structured LLM is not configured. Wire a real model client before using the LLM-based clinical agent."
        )
