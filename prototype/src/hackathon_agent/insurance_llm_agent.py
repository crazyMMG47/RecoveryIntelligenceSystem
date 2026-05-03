from __future__ import annotations

from .insurance_contract import APPEAL_RISK_CODE_ALIASES, validate_insurance_output
from .insurance_prompt import ALLOWED_APPEAL_RISK_CODES, ALLOWED_NEXT_STEPS, build_insurance_messages
from .insurance_retriever import InsurancePolicyRetriever
from .llm import PromptMessage, StructuredLLM
from .schemas import (
    ConfidenceLevel,
    CoverageDecision,
    InsuranceAgentInput,
    InsuranceAgentOutput,
    InsuranceDecision,
    RequirementStatus,
)


def _auto_recover(result: InsuranceAgentOutput) -> InsuranceAgentOutput:
    """Apply rule-based fixes to common LLM output errors without an LLM round-trip.

    Returns a new InsuranceAgentOutput if any fix was applied, or the original object.
    """
    changed = False
    kwargs = result.model_dump(mode="python")

    # Fix 1: likely_covered + unresolved requirements → conditionally_covered_pending_documentation
    unresolved = [
        item.code
        for item in result.requirements
        if item.status != RequirementStatus.SATISFIED
    ]
    if (
        result.decision.coverage_position == CoverageDecision.LIKELY_COVERED
        and unresolved
    ):
        kwargs["decision"] = result.decision.model_copy(
            update={"coverage_position": CoverageDecision.CONDITIONALLY_COVERED}
        )
        changed = True

    # Fix 2: remap near-miss appeal_risk_factors.code values via alias table
    fixed_risks = []
    for risk in result.appeal_risk_factors:
        resolved = APPEAL_RISK_CODE_ALIASES.get(risk.code, risk.code)
        if resolved in ALLOWED_APPEAL_RISK_CODES and resolved != risk.code:
            fixed_risks.append(risk.model_copy(update={"code": resolved}))
            changed = True
        elif resolved in ALLOWED_APPEAL_RISK_CODES:
            fixed_risks.append(risk)
        else:
            # Drop entirely — invalid code with no alias, cleaner than crashing
            changed = True
    if changed:
        kwargs["appeal_risk_factors"] = fixed_risks

    if not changed:
        return result
    return InsuranceAgentOutput(**kwargs)


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
        last_result: InsuranceAgentOutput | None = None

        for attempt in range(3):
            try:
                last_result = self.llm.generate_structured(
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
                break

            errors = validate_insurance_output(
                payload=payload,
                retrieved_policy=self.retriever.flatten(retrieved_buckets),
                result=last_result,
            )
            if not errors:
                return last_result

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
                if any("conditionally_covered_pending_documentation" in error for error in errors):
                    extra_instruction += (
                        "\nWhen documentation is missing or unresolved, use "
                        "coverage_position = 'conditionally_covered_pending_documentation', "
                        "not 'likely_covered'."
                    )
                messages = messages + [
                    PromptMessage(
                        role="user",
                        content=(
                            "Your previous response violated the contract. "
                            "Return a corrected InsuranceAgentOutput only.\n"
                            "Allowed next_steps values are exactly:\n"
                            + "\n".join(f"- {step}" for step in ALLOWED_NEXT_STEPS)
                            + "\nAllowed appeal_risk_factors.code values are exactly:\n"
                            + "\n".join(f"- {code}" for code in ALLOWED_APPEAL_RISK_CODES)
                            + "\n"
                            + "\n".join(f"- {error}" for error in errors)
                            + extra_instruction
                        ),
                    )
                ]

        # All retries exhausted — try rule-based auto-recovery before giving up.
        if last_result is not None:
            recovered = _auto_recover(last_result)
            recovery_errors = validate_insurance_output(
                payload=payload,
                retrieved_policy=self.retriever.flatten(retrieved_buckets),
                result=recovered,
            )
            if not recovery_errors:
                return recovered

        # Return a structured degraded response rather than crashing the demo.
        return InsuranceAgentOutput(
            decision=InsuranceDecision(
                coverage_position=CoverageDecision.UNCLEAR,
                review_needed=True,
                decision_drivers=[],
            ),
            coverage_rules=[],
            requirements=[],
            appeal_risk_factors=[],
            next_steps=[],
            confidence=ConfidenceLevel("low"),
            validation_errors=last_errors or (
                [str(last_exception)] if last_exception else ["Unknown validation failure."]
            ),
        )
