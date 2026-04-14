from __future__ import annotations

from .schemas import ClinicalAgentInput, ClinicalAgentOutput, SourceType


ALLOWED_RECOMMENDED_SERVICES = {
    "supervised_pt",
    "surgical_eval",
}

ALLOWED_REASON_CODES = {
    "documented_quadriceps_weakness",
    "documented_neuromuscular_deficit",
    "documented_activity_related_pain",
    "documented_persistent_instability",
    "no_acute_structural_failure_on_imaging",
    "post_revision_rehab_incomplete",
    "possible_acute_structural_failure",
    "fear_of_reinjury",
}

ALLOWED_EVIDENCE_CODES = set(ALLOWED_REASON_CODES)

ALLOWED_REQUIREMENT_CODES = {
    "document_prior_rehab_gap",
    "objective_deficit_measurement",
    "structured_pt_plan_definition",
}

ALLOWED_RISK_CODES = {
    "fear_of_reinjury",
    "early_cartilage_degeneration",
    "persistent_activity_related_pain",
}

ALLOWED_NEXT_STEPS = {
    "collect_objective_strength_testing",
    "collect_single_leg_functional_testing",
    "define_supervised_pt_block",
    "reassess_after_pt_block",
    "consider_surgical_reassessment",
}

ALLOWED_STOP_CONDITIONS = {
    "new_acute_tear_identified",
    "progressive_instability_after_structured_pt",
    "worsening_function_despite_structured_pt",
}


def build_allowed_source_refs(payload: ClinicalAgentInput) -> list[str]:
    refs = ["patient_summary"]
    refs.extend(f"clinical_notes[{i}]" for i, _ in enumerate(payload.clinical_notes))
    refs.extend(f"pt_notes[{i}]" for i, _ in enumerate(payload.pt_notes))
    refs.extend(f"imaging[{i}]" for i, _ in enumerate(payload.imaging))
    return refs


def validate_clinical_output(
    payload: ClinicalAgentInput,
    result: ClinicalAgentOutput,
) -> list[str]:
    errors: list[str] = []
    allowed_source_refs = set(build_allowed_source_refs(payload))

    if result.decision.recommended_service not in ALLOWED_RECOMMENDED_SERVICES:
        errors.append(
            f"recommended_service must be one of {sorted(ALLOWED_RECOMMENDED_SERVICES)}."
        )

    invalid_reason_codes = [
        code
        for code in result.decision.recommendation_reason_codes
        if code not in ALLOWED_REASON_CODES
    ]
    if invalid_reason_codes:
        errors.append(
            f"recommendation_reason_codes contains unsupported values: {invalid_reason_codes}."
        )

    for evidence in result.evidence:
        if evidence.code not in ALLOWED_EVIDENCE_CODES:
            errors.append(f"evidence.code '{evidence.code}' is not in the allowed clinical vocabulary.")
        if evidence.source_ref not in allowed_source_refs:
            errors.append(f"evidence.source_ref '{evidence.source_ref}' does not map to the provided input.")
        if evidence.source_type == SourceType.PATIENT_SUMMARY and evidence.source_ref != "patient_summary":
            errors.append("patient_summary evidence must use source_ref 'patient_summary'.")
        if evidence.source_type == SourceType.CLINICAL_NOTE and not evidence.source_ref.startswith("clinical_notes["):
            errors.append("clinical_note evidence must reference 'clinical_notes[i]'.")
        if evidence.source_type == SourceType.PT_NOTE and not evidence.source_ref.startswith("pt_notes["):
            errors.append("pt_note evidence must reference 'pt_notes[i]'.")
        if evidence.source_type == SourceType.IMAGING and not evidence.source_ref.startswith("imaging["):
            errors.append("imaging evidence must reference 'imaging[i]'.")

    for requirement in result.requirements:
        if requirement.code not in ALLOWED_REQUIREMENT_CODES:
            errors.append(
                f"requirement.code '{requirement.code}' is not in the allowed clinical vocabulary."
            )

    for risk_item in result.risk_items:
        if risk_item.code not in ALLOWED_RISK_CODES:
            errors.append(
                f"risk_items.code '{risk_item.code}' is not in the allowed clinical vocabulary."
            )

    invalid_next_steps = [step for step in result.next_steps if step not in ALLOWED_NEXT_STEPS]
    if invalid_next_steps:
        errors.append(f"next_steps contains unsupported values: {invalid_next_steps}.")

    invalid_stop_conditions = [
        step for step in result.stop_conditions if step not in ALLOWED_STOP_CONDITIONS
    ]
    if invalid_stop_conditions:
        errors.append(f"stop_conditions contains unsupported values: {invalid_stop_conditions}.")

    if result.decision.recommended_path.value == "additional_structured_pt":
        supports_pt = any(item.supports == "supervised_pt" for item in result.evidence)
        if not supports_pt:
            errors.append("recommended_path is additional_structured_pt but evidence does not support supervised_pt.")

    if result.confidence.value == "high" and len(result.evidence) < 2:
        errors.append("high confidence requires at least two evidence items.")

    return errors
