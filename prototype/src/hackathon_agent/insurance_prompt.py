from __future__ import annotations

import json

from ...kp.bucketed_policy_retriever import EvidenceBucket
from .llm import PromptMessage
from .schemas import InsuranceAgentInput


ALLOWED_REQUIREMENT_CODES = [
    "physician_justification_note",
    "objective_functional_measurements",
    "structured_therapy_plan",
    "document_incomplete_rehab_course",
]

ALLOWED_NEXT_STEPS = [
    "attach_physician_justification_note",
    "attach_objective_deficit_measurements",
    "attach_structured_pt_plan",
    "add_context_for_attendance_interruptions",
]

ALLOWED_DECISION_DRIVERS = [
    "physician_justification",
    "objective_functional_deficit",
    "therapy_plan",
    "incomplete_prior_rehab_supports_request",
    "clinical_path_not_pt",
    "missing_policy_support",
    "missing_required_documentation",
]

ALLOWED_COVERAGE_RULE_IDS = [
    "physician_justification_required",
    "objective_deficit_required",
    "therapy_plan_required",
    "adherence_history_review",
    "incomplete_rehab_history_supports_request",
]


INSURANCE_SYSTEM_PROMPT_TEMPLATE = """
You are the Insurance Agent in a multi-agent healthcare workflow.

Your job is to review the requested clinical service against the retrieved insurance policy evidence
and return only structured insurance output.

You are given bucketed policy evidence. Each bucket represents a different insurance decision dimension.
Use the buckets to reason systematically.

Rules:
- Do not rewrite the clinical recommendation.
- Do not invent policy language or coverage rules.
- Use only information present in the provided clinical input and retrieved bucket evidence.
- If policy support is unclear, return unclear rather than inventing certainty.
- If important buckets are weak or underfilled, lower your confidence.
- Return an InsuranceAgentOutput object only.
- All code-like fields must use only the allowed internal vocabulary shown below.

Allowed requirement.code values:
{allowed_requirement_codes}

Allowed next_steps values:
{allowed_next_steps}

Allowed decision.decision_drivers values:
{allowed_decision_drivers}

Allowed coverage_rules.rule_id values:
{allowed_coverage_rule_ids}

Interpret the buckets as follows:
- coverage_rules: applicable plan / policy / benefit language
- medical_necessity: support for continuation or medical necessity
- documentation_requirements: what documents or structured evidence must be present
- stop_or_escalate: reasons therapy may stop, be denied, require escalation, continuity handling, or re-authorization

Use these exact mappings:
- physician justification requirement -> physician_justification_note
- measurable functional deficits -> objective_functional_measurements
- clear therapy plan -> structured_therapy_plan
- documentation of incomplete prior rehab -> document_incomplete_rehab_course

Use these exact next step mappings:
- attach physician note -> attach_physician_justification_note
- attach objective deficit measurements -> attach_objective_deficit_measurements
- attach structured PT plan -> attach_structured_pt_plan

Use these exact rule_id mappings:
- physician justification rule -> physician_justification_required
- measurable deficit rule -> objective_deficit_required
- therapy plan rule -> therapy_plan_required
- adherence history review rule -> adherence_history_review
- incomplete rehab history support rule -> incomplete_rehab_history_supports_request
""".strip()


def build_insurance_messages(
    payload: InsuranceAgentInput,
    retrieved_buckets: list[EvidenceBucket],
) -> list[PromptMessage]:
    bucket_context = []
    for bucket in retrieved_buckets:
        bucket_context.append(
            {
                "bucket_name": bucket.bucket_name,
                "query": bucket.query,
                "confidence": bucket.confidence,
                "notes": bucket.notes,
                "chunks": [
                    {
                        "source_ref": chunk.source_ref,
                        "title": chunk.title,
                        "section": chunk.section,
                        "text": chunk.text,
                        "url": chunk.url,
                    }
                    for chunk in bucket.chunks
                ],
            }
        )

    example_json = {
        "decision": {
            "coverage_position": "unclear",
            "review_needed": True,
            "decision_drivers": [
                "physician_justification",
                "objective_functional_deficit",
                "therapy_plan",
                "incomplete_prior_rehab_supports_request",
            ],
        },
        "coverage_rules": [
            {
                "rule_id": "physician_justification_required",
                "rule_text": "Higher-frequency PT requires physician justification.",
                "effect": "supporting_if_satisfied",
                "satisfied_by": [],
                "unsatisfied_reason": "missing_physician_note",
            },
            {
                "rule_id": "objective_deficit_required",
                "rule_text": "Extended PT requests should document measurable functional deficits.",
                "effect": "supporting_if_satisfied",
                "satisfied_by": ["documented_quadriceps_weakness"],
                "unsatisfied_reason": "missing_objective_measurements",
            },
        ],
        "requirements": [
            {
                "code": "physician_justification_note",
                "description": "Physician note requesting 2x/week PT is required.",
                "owner": "insurance",
                "status": "unsatisfied",
            },
            {
                "code": "objective_functional_measurements",
                "description": "Objective strength and movement deficit measurements are needed for utilization review.",
                "owner": "insurance",
                "status": "unsatisfied",
            },
            {
                "code": "structured_therapy_plan",
                "description": "Structured PT plan with goals, frequency, and reassessment timing is required.",
                "owner": "insurance",
                "status": "unsatisfied",
            },
        ],
        "appeal_risk_factors": [],
        "next_steps": [
            "attach_physician_justification_note",
            "attach_objective_deficit_measurements",
            "attach_structured_pt_plan",
        ],
        "confidence": "medium",
    }

    user_payload = {
        "question": payload.question,
        "clinical_decision": payload.clinical_decision.model_dump(),
        "clinical_evidence": [item.model_dump() for item in payload.clinical_evidence],
        "clinical_requirements": [item.model_dump() for item in payload.clinical_requirements],
        "retrieved_buckets": bucket_context,
    }

    system_prompt = INSURANCE_SYSTEM_PROMPT_TEMPLATE.format(
        allowed_requirement_codes=json.dumps(ALLOWED_REQUIREMENT_CODES, indent=2),
        allowed_next_steps=json.dumps(ALLOWED_NEXT_STEPS, indent=2),
        allowed_decision_drivers=json.dumps(ALLOWED_DECISION_DRIVERS, indent=2),
        allowed_coverage_rule_ids=json.dumps(ALLOWED_COVERAGE_RULE_IDS, indent=2),
    )

    return [
        PromptMessage(role="system", content=system_prompt),
        PromptMessage(
            role="user",
            content=(
                "Use the following example shape as guidance:\n"
                f"{json.dumps(example_json, ensure_ascii=True, indent=2)}\n\n"
                "Now return an InsuranceAgentOutput object for the following case:\n"
                f"{json.dumps(user_payload, ensure_ascii=True, indent=2)}"
            ),
        ),
    ]