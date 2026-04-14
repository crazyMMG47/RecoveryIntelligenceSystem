from __future__ import annotations

from dataclasses import dataclass

from .schemas import InsuranceAgentInput


@dataclass(frozen=True)
class RetrievedPolicyChunk:
    source_ref: str
    title: str
    text: str
    url: str | None = None


class PolicyRetriever:
    """
    Prototype retrieval layer for insurance policy context.

    Current behavior:
    - If policy_text is already provided in InsuranceAgentInput, wrap it as one chunk.
    - Later, replace this with:
      - insurer website retrieval
      - indexed policy docs
      - vector DB retrieval
      - PDF parsing / chunk search
    """

    def retrieve(self, payload: InsuranceAgentInput) -> list[RetrievedPolicyChunk]:
        policy_text = payload.policy_text.strip()
        if not policy_text:
            return []

        return [
            RetrievedPolicyChunk(
                source_ref="policy_text",
                title="Provided policy text",
                text=policy_text,
                url=None,
            )
        ]