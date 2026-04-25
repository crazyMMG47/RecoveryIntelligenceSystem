from __future__ import annotations

from .insurance_contract import validate_insurance_output
from .insurance_prompt import ALLOWED_NEXT_STEPS, build_insurance_messages
from .insurance_retriever import InsurancePolicyRetriever
from .llm import PromptMessage, StructuredLLM
from .schemas import InsuranceAgentInput, InsuranceAgentOutput


class InsuranceLLMAgent:
    def __init__(
        self,
        llm: StructuredLLM,
        retriever: InsurancePolicyRetriever,
        *,
        debug: bool = False,
    ) -> None:
        self.llm = llm
        self.retriever = retriever
        self.debug = debug

    def run(self, payload: InsuranceAgentInput) -> InsuranceAgentOutput:
        retrieved_buckets = self.retriever.retrieve(payload)

        if self.debug:
            for bucket in retrieved_buckets:
                print(f"[insurance] bucket={bucket.bucket_name} confidence={bucket.confidence:.2f}")
                for chunk in bucket.chunks:
                    print(f"  - {chunk.source_ref}: {chunk.text}")

        messages = build_insurance_messages(
            payload=payload,
            retrieved_buckets=retrieved_buckets,
        )
        last_errors: list[str] = []
        last_exception: Exception | None = None

        for attempt in range(3):
            try:
                result = self.llm.generate_structured(
                    messages=messages,
                    response_model=InsuranceAgentOutput,
                )
            except RuntimeError as exc:
                last_exception = exc
                if attempt < 2:
                    messages = messages + [
                        PromptMessage(
                            role="user",
                            content=(
                                "Your previous response was not valid JSON. "
                                "Retry with a shorter InsuranceAgentOutput only.\n"
                                "Keep rule_text short, do not quote long policy passages, "
                                "and keep arrays minimal."
                            ),
                        )
                    ]
                    continue
                raise

            errors = validate_insurance_output(
                payload=payload,
                retrieved_policy=self.retriever.flatten(retrieved_buckets),
                result=result,
            )
            if not errors:
                return result

            last_errors = errors
            if attempt < 2:
                extra_instruction = ""
                if any(
                    "incomplete_rehab_history_supports_request" in error
                    for error in errors
                ):
                    extra_instruction = (
                        "\nIf post_revision_rehab_incomplete exists in clinical_evidence_codes, "
                        "then incomplete_rehab_history_supports_request must be satisfied by that code "
                        "and unsatisfied_reason must be empty."
                    )
                messages = messages + [
                    PromptMessage(
                        role="user",
                        content=(
                            "Your previous response violated the contract. "
                            "Return a corrected InsuranceAgentOutput only.\n"
                            "Allowed next_steps values are exactly:\n"
                            + "\n".join(f"- {step}" for step in ALLOWED_NEXT_STEPS)
                            + "\n"
                            + "\n".join(f"- {error}" for error in errors)
                            + extra_instruction
                        ),
                    )
                ]

        raise RuntimeError(
            "Insurance LLM output failed semantic validation:\n"
            + "\n".join(f"- {error}" for error in last_errors)
            + (f"\nLast exception: {last_exception}" if last_exception else "")
        )
