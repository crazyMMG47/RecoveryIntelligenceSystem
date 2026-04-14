from __future__ import annotations

from .clinical_contract import validate_clinical_output
from .clinical_prompt import build_clinical_messages
from .llm import PromptMessage, StructuredLLM
from .schemas import ClinicalAgentInput, ClinicalAgentOutput


class ClinicalLLMAgent:
    def __init__(self, llm: StructuredLLM) -> None:
        self.llm = llm

    def run(self, payload: ClinicalAgentInput) -> ClinicalAgentOutput:
        messages = build_clinical_messages(payload)
        last_errors: list[str] = []

        for attempt in range(2):
            result = self.llm.generate_structured(
                messages=messages,
                response_model=ClinicalAgentOutput,
            )
            errors = validate_clinical_output(payload, result)
            if not errors:
                return result

            last_errors = errors
            if attempt == 0:
                messages = messages + [
                    PromptMessage(
                        role="user",
                        content=(
                            "Your previous response violated the contract. "
                            "Return a corrected ClinicalAgentOutput only.\n"
                            + "\n".join(f"- {error}" for error in errors)
                        ),
                    )
                ]

        raise RuntimeError(
            "Clinical LLM output failed semantic validation:\n"
            + "\n".join(f"- {error}" for error in last_errors)
        )
