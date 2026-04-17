from __future__ import annotations

from ...kp.bucketed_policy_retriever import BucketedPolicyRetriever, EvidenceBucket
from .insurance_contract import validate_insurance_output
from .insurance_prompt import build_insurance_messages
from .llm import PromptMessage, StructuredLLM
from .schemas import InsuranceAgentInput, InsuranceAgentOutput


def _normalize_insurance_output(result: InsuranceAgentOutput) -> InsuranceAgentOutput:
    requirement_map = {
        "physician_justification": "physician_justification_note",
        "measurable_functional_deficits": "objective_functional_measurements",
        "clear_therapy_plan": "structured_therapy_plan",
        "prior_rehab_documentation": "document_incomplete_rehab_course",
    }

    next_step_map = {
        "attach_physician_justification": "attach_physician_justification_note",
        "attach_measurable_functional_deficits": "attach_objective_deficit_measurements",
        "attach_clear_therapy_plan": "attach_structured_pt_plan",
        "attach_prior_rehab_documentation": "add_context_for_attendance_interruptions",
    }

    rule_id_map = {
        "two_sessions_per_week_requires_justification": "physician_justification_required",
        "extended_pt_requires_measurable_deficits": "objective_deficit_required",
        "extended_pt_requires_clear_therapy_plan": "therapy_plan_required",
        "prior_rehab_completion_impacts_approval": "incomplete_rehab_history_supports_request",
    }

    for req in result.requirements:
        req.code = requirement_map.get(req.code, req.code)

    result.next_steps = [next_step_map.get(step, step) for step in result.next_steps]

    for rule in result.coverage_rules:
        rule.rule_id = rule_id_map.get(rule.rule_id, rule.rule_id)

    return result


class InsuranceLLMAgent:
    def __init__(
        self,
        llm: StructuredLLM,
        retriever: BucketedPolicyRetriever,
        *,
        debug: bool = False,
    ) -> None:
        self.llm = llm
        self.retriever = retriever
        self.debug = debug

    def run(self, payload: InsuranceAgentInput) -> InsuranceAgentOutput:
        retrieved_buckets = self.retriever.retrieve(payload)

        if self.debug:
            print("\n=== Retrieved Evidence Buckets ===")
            if not retrieved_buckets:
                print("[WARN] No evidence buckets retrieved.")

            for bucket in retrieved_buckets:
                print(f"\n=== Bucket: {bucket.bucket_name} ===")
                print(f"Query: {bucket.query}")
                print(f"Confidence: {bucket.confidence:.2f}")
                for note in bucket.notes:
                    print(f"Note: {note}")

                if not bucket.chunks:
                    print("[WARN] No chunks in this bucket.")

                for i, chunk in enumerate(bucket.chunks, start=1):
                    print(f"\n--- Chunk {i} ---")
                    print(f"source_ref: {chunk.source_ref}")
                    print(f"title: {chunk.title}")
                    print(f"section: {chunk.section}")
                    print(f"url: {chunk.url}")
                    print(chunk.text[:800])

        messages = build_insurance_messages(
            payload=payload,
            retrieved_buckets=retrieved_buckets,
        )

        last_errors: list[str] = []

        for attempt in range(2):
            result = self.llm.generate_structured(
                messages=messages,
                response_model=InsuranceAgentOutput,
            )

            result = _normalize_insurance_output(result)

            # flatten bucket chunks for current validator compatibility
            flat_chunks = self.retriever.flatten_buckets(retrieved_buckets)

            errors = validate_insurance_output(
                payload=payload,
                retrieved_policy=flat_chunks,
                result=result,
            )
            if not errors:
                return result

            last_errors = errors
            if attempt == 0:
                messages = messages + [
                    PromptMessage(
                        role="user",
                        content=(
                            "Your previous response violated the contract. "
                            "Return a corrected InsuranceAgentOutput only.\n"
                            + "\n".join(f"- {error}" for error in errors)
                        ),
                    )
                ]

        raise RuntimeError(
            "Insurance LLM output failed semantic validation:\n"
            + "\n".join(f"- {error}" for error in last_errors)
        )