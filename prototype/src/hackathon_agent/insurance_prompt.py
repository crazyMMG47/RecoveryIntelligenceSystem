from __future__ import annotations

import json
import re

from .insurance_retriever import EvidenceBucket
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
    "attach_prior_rehab_documentation",
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

INSURANCE_SYSTEM_PROMPT = """
You are the Insurance Agent in a multi-agent healthcare workflow.

Your job is to review the requested clinical service against retrieved insurance
policy evidence and return only structured insurance output.

Rules:
- Do not rewrite the clinical recommendation.
- Do not invent policy language or coverage rules.
- Use only the clinical input and retrieved policy buckets provided below.
- If policy support is unclear, return unclear.
- If required documentation is missing, reflect it in requirements and next_steps.
- Lower confidence when bucket evidence is weak or sparse.
- Return an InsuranceAgentOutput object only.
- All code-like fields must use only the allowed internal vocabulary shown below.
- Keep the output compact. Do not quote or paraphrase long policy passages.
- Keep each coverage_rules.rule_text under 220 characters.
- Return at most 4 coverage_rules, 4 requirements, 2 appeal_risk_factors, and 5 next_steps.

Allowed requirement.code values:
{allowed_requirement_codes}

Allowed next_steps values:
{allowed_next_steps}

Allowed decision.decision_drivers values:
{allowed_decision_drivers}

Allowed coverage_rules.rule_id values:
{allowed_coverage_rule_ids}

Use the evidence buckets as follows:
- coverage_rules: plan or benefit language that governs approval
- medical_necessity: support for continued PT or evidence that rehab remains indicated
- documentation_requirements: physician note, therapy plan, measurements, reassessment
- stop_or_escalate: adherence, denial risk, escalation, review triggers

Use these exact mappings when supported by the evidence:
- physician justification requirement -> physician_justification_note
- measurable functional deficits -> objective_functional_measurements
- clear therapy plan -> structured_therapy_plan
- incomplete prior rehab documentation -> document_incomplete_rehab_course

Critical consistency rules:
- If clinical_evidence_codes contains post_revision_rehab_incomplete and you output coverage_rules.rule_id = incomplete_rehab_history_supports_request, that rule must be supportive, satisfied_by must include post_revision_rehab_incomplete, and unsatisfied_reason must be empty.
- Do not mark incomplete_rehab_history_supports_request as unsatisfied when post_revision_rehab_incomplete is present in the clinical evidence.

Use these exact next-step mappings:
- attach physician note -> attach_physician_justification_note
- attach objective deficit measurements -> attach_objective_deficit_measurements
- attach structured PT plan -> attach_structured_pt_plan
- attach prior rehab documentation -> attach_prior_rehab_documentation
- add context for interrupted attendance -> add_context_for_attendance_interruptions

Forbidden near-miss values:
- Do not output add_context_for_interrupted_attendance
""".strip()


def _compact_text(text: str, *, max_chars: int = 320) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def build_insurance_messages(
    payload: InsuranceAgentInput,
    retrieved_buckets: list[EvidenceBucket],
) -> list[PromptMessage]:
    bucket_context = [
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
                    "excerpt": _compact_text(chunk.text),
                    "bucket": chunk.bucket,
                    "url": chunk.url,
                    "source_type": chunk.source_type,
                }
                for chunk in bucket.chunks
            ],
        }
        for bucket in retrieved_buckets
    ]

    example_json = {
        "decision": {
            "coverage_position": "unclear",
            "review_needed": True,
            "decision_drivers": [
                "physician_justification",
                "objective_functional_deficit",
                "therapy_plan",
            ],
        },
        "coverage_rules": [
            {
                "rule_id": "physician_justification_required",
                "rule_text": "Two sessions per week requires physician justification and utilization review.",
                "effect": "supporting_if_satisfied",
                "satisfied_by": [],
                "unsatisfied_reason": "missing_physician_note",
            }
        ],
        "requirements": [
            {
                "code": "physician_justification_note",
                "description": "Physician note requesting 2x/week PT is required.",
                "owner": "insurance",
                "status": "unsatisfied",
            }
        ],
        "appeal_risk_factors": [],
        "next_steps": [
            "attach_physician_justification_note",
            "attach_objective_deficit_measurements",
            "attach_prior_rehab_documentation",
            "add_context_for_attendance_interruptions",
        ],
        "confidence": "medium",
    }

    user_payload = {
        "question": payload.question,
        "clinical_decision": payload.clinical_decision.model_dump(mode="json"),
        "clinical_evidence_codes": [item.code for item in payload.clinical_evidence],
        "clinical_evidence": [item.model_dump(mode="json") for item in payload.clinical_evidence],
        "clinical_requirements": [item.model_dump(mode="json") for item in payload.clinical_requirements],
        "retrieved_buckets": bucket_context,
    }

    system_prompt = INSURANCE_SYSTEM_PROMPT.format(
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
