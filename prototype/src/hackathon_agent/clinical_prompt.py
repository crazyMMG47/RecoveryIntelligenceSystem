from __future__ import annotations

import json

from .clinical_contract import (
    ALLOWED_EVIDENCE_CODES,
    ALLOWED_NEXT_STEPS,
    ALLOWED_REASON_CODES,
    ALLOWED_REQUIREMENT_CODES,
    ALLOWED_RECOMMENDED_SERVICES,
    ALLOWED_RISK_CODES,
    ALLOWED_STOP_CONDITIONS,
    build_allowed_source_refs,
)
from .llm import PromptMessage
from .schemas import ClinicalAgentInput


CLINICAL_SYSTEM_PROMPT_TEMPLATE = """
You are the Clinical Agent in a multi-agent healthcare workflow.

Your job is to read patient summary, clinical notes, PT notes, and imaging descriptions and return only structured clinical output.

Rules:
- Do not answer the user directly.
- Do not write a narrative summary outside the schema.
- Do not mention insurance coverage, policy, approval, or billing.
- Use only information present in the provided input.
- If information is missing, encode that in requirements or low confidence instead of inventing data.
- Build the output in this order: evidence and requirements first, then decision, then confidence and next steps.
- Do not generate ICD, CPT, SNOMED, or diagnosis billing codes.
- All code-like fields must use only the allowed internal vocabulary shown below.

Allowed recommended_service values:
{allowed_recommended_services}

Allowed recommendation_reason_codes and evidence.code values:
{allowed_reason_codes}

Allowed requirement.code values:
{allowed_requirement_codes}

Allowed risk_items.code values:
{allowed_risk_codes}

Allowed next_steps values:
{allowed_next_steps}

Allowed stop_conditions values:
{allowed_stop_conditions}

Allowed source_ref values for this request:
{allowed_source_refs}

Field rules:
- recommendation_reason_codes must reuse the same internal codes that appear in evidence.code.
- evidence.statement must be atomic and source-linked.
- source_type and source_ref must match exactly.
- requirement descriptions must describe clinical prerequisites or missing clinical data only.
- next_steps must be short action codes from the allowed set, not prose.
- If no allowed code fits, lower confidence or add a requirement instead of inventing a new code.

Output shape example:
{example_json}
""".strip()


def build_clinical_messages(payload: ClinicalAgentInput) -> list[PromptMessage]:
    allowed_source_refs = build_allowed_source_refs(payload)
    example_json = {
        "decision": {
            "recommended_service": "supervised_pt",
            "recommendation_disposition": "recommend",
            "recommended_path": "additional_structured_pt",
            "recommendation_reason_codes": [
                "documented_quadriceps_weakness",
                "post_revision_rehab_incomplete",
            ],
        },
        "evidence": [
            {
                "code": "documented_quadriceps_weakness",
                "statement": "Quadriceps weakness is documented.",
                "source_type": "pt_note",
                "source_ref": "pt_notes[0]",
                "supports": "supervised_pt",
                "strength": "strong",
            }
        ],
        "requirements": [
            {
                "code": "objective_deficit_measurement",
                "description": "Need objective strength and movement testing.",
                "owner": "clinical",
                "status": "unsatisfied",
            }
        ],
        "risk_items": [],
        "stop_conditions": ["new_acute_tear_identified"],
        "next_steps": [
            "collect_objective_strength_testing",
            "define_supervised_pt_block",
        ],
        "confidence": "medium",
    }
    system_prompt = CLINICAL_SYSTEM_PROMPT_TEMPLATE.format(
        allowed_recommended_services=sorted(ALLOWED_RECOMMENDED_SERVICES),
        allowed_reason_codes=sorted(ALLOWED_REASON_CODES),
        allowed_requirement_codes=sorted(ALLOWED_REQUIREMENT_CODES),
        allowed_risk_codes=sorted(ALLOWED_RISK_CODES),
        allowed_next_steps=sorted(ALLOWED_NEXT_STEPS),
        allowed_stop_conditions=sorted(ALLOWED_STOP_CONDITIONS),
        allowed_source_refs=allowed_source_refs,
        example_json=json.dumps(example_json, ensure_ascii=True, indent=2),
    )
    user_payload = {
        "question": payload.question,
        "patient_summary": payload.patient_summary,
        "clinical_notes": payload.clinical_notes,
        "pt_notes": payload.pt_notes,
        "imaging": payload.imaging,
    }
    return [
        PromptMessage(role="system", content=system_prompt),
        PromptMessage(
            role="user",
            content=(
                "Return a ClinicalAgentOutput object for the following case.\n"
                f"{json.dumps(user_payload, ensure_ascii=True, indent=2)}"
            ),
        ),
    ]
