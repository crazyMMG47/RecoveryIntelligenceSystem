from __future__ import annotations

from .insurance_prompt import (
    ALLOWED_COVERAGE_RULE_IDS,
    ALLOWED_DECISION_DRIVERS,
    ALLOWED_NEXT_STEPS,
    ALLOWED_REQUIREMENT_CODES,
)
from .insurance_retriever import RetrievedPolicyChunk
from .schemas import (
    CarePath,
    InsuranceAgentInput,
    InsuranceAgentOutput,
    RequirementStatus,
    WorkflowOwner,
)


ALLOWED_APPEAL_RISK_CODES = {
    "attendance_interruptions_may_reduce_approval_strength",
}

REQUIREMENT_NEXT_STEP_MAP = {
    "physician_justification_note": "attach_physician_justification_note",
    "objective_functional_measurements": "attach_objective_deficit_measurements",
    "structured_therapy_plan": "attach_structured_pt_plan",
    "document_incomplete_rehab_course": "attach_prior_rehab_documentation",
}


def validate_insurance_output(
    payload: InsuranceAgentInput,
    retrieved_policy: list[RetrievedPolicyChunk],
    result: InsuranceAgentOutput,
) -> list[str]:
    errors: list[str] = []
    clinical_codes = {item.code for item in payload.clinical_evidence}

    invalid_decision_drivers = [
        code for code in result.decision.decision_drivers
        if code not in ALLOWED_DECISION_DRIVERS
    ]
    if invalid_decision_drivers:
        errors.append(
            f"decision.decision_drivers contains unsupported values: {invalid_decision_drivers}."
        )

    for requirement in result.requirements:
        if requirement.code not in ALLOWED_REQUIREMENT_CODES:
            errors.append(
                f"requirement.code '{requirement.code}' is not allowed."
            )
        if requirement.owner != WorkflowOwner.INSURANCE:
            errors.append(
                f"requirement.owner for '{requirement.code}' must be 'insurance'."
            )

    invalid_next_steps = [
        step for step in result.next_steps
        if step not in ALLOWED_NEXT_STEPS
    ]
    if invalid_next_steps:
        errors.append(f"next_steps contains unsupported values: {invalid_next_steps}.")

    for risk_item in result.appeal_risk_factors:
        if risk_item.code not in ALLOWED_APPEAL_RISK_CODES:
            errors.append(
                f"appeal_risk_factors.code '{risk_item.code}' is not allowed."
            )

    for rule in result.coverage_rules:
        if rule.rule_id not in ALLOWED_COVERAGE_RULE_IDS:
            errors.append(
                f"coverage_rules.rule_id '{rule.rule_id}' is not allowed."
            )
        if not rule.rule_text.strip():
            errors.append(f"coverage rule '{rule.rule_id}' must include rule_text.")
        if not rule.effect.strip():
            errors.append(f"coverage rule '{rule.rule_id}' must include effect.")

    if not retrieved_policy and result.confidence.value == "high":
        errors.append(
            "high confidence is not allowed when no policy evidence was retrieved."
        )

    if (
        result.decision.coverage_position.value == "unclear"
        and result.confidence.value == "high"
    ):
        errors.append(
            "high confidence is not allowed when coverage_position is unclear."
        )

    if (
        payload.clinical_decision.recommended_path != CarePath.ADDITIONAL_STRUCTURED_PT
        and result.decision.coverage_position.value == "likely_covered"
    ):
        errors.append(
            "coverage_position cannot be likely_covered when the clinical path is not additional_structured_pt."
        )

    if result.decision.coverage_position.value == "likely_covered":
        unresolved_requirements = [
            item.code
            for item in result.requirements
            if item.status != RequirementStatus.SATISFIED
        ]
        if unresolved_requirements:
            errors.append(
                "coverage_position is likely_covered but unresolved requirements remain: "
                f"{unresolved_requirements}."
            )

    unresolved_requirements = [
        item.code
        for item in result.requirements
        if item.status != RequirementStatus.SATISFIED
    ]
    if unresolved_requirements and result.confidence.value == "high":
        errors.append(
            "high confidence is not allowed while unresolved insurance requirements remain."
        )

    for requirement_code in unresolved_requirements:
        expected_step = REQUIREMENT_NEXT_STEP_MAP.get(requirement_code)
        if expected_step and expected_step not in result.next_steps:
            errors.append(
                f"unsatisfied requirement '{requirement_code}' requires next step '{expected_step}'."
            )

    if "physician_justification" in result.decision.decision_drivers:
        has_signal = any(
            rule.rule_id == "physician_justification_required"
            for rule in result.coverage_rules
        ) or any(
            requirement.code == "physician_justification_note"
            for requirement in result.requirements
        )
        if not has_signal:
            errors.append(
                "decision driver 'physician_justification' requires a matching rule or requirement."
            )

    if "objective_functional_deficit" in result.decision.decision_drivers:
        has_signal = any(
            rule.rule_id == "objective_deficit_required"
            for rule in result.coverage_rules
        ) or bool(
            {"documented_quadriceps_weakness", "documented_neuromuscular_deficit"} & clinical_codes
        )
        if not has_signal:
            errors.append(
                "decision driver 'objective_functional_deficit' is unsupported by policy rule or clinical evidence."
            )

    if "therapy_plan" in result.decision.decision_drivers:
        has_signal = any(
            rule.rule_id == "therapy_plan_required"
            for rule in result.coverage_rules
        ) or any(
            requirement.code == "structured_therapy_plan"
            for requirement in result.requirements
        )
        if not has_signal:
            errors.append(
                "decision driver 'therapy_plan' requires a matching rule or requirement."
            )

    if "incomplete_prior_rehab_supports_request" in result.decision.decision_drivers:
        if "post_revision_rehab_incomplete" not in clinical_codes:
            errors.append(
                "decision driver 'incomplete_prior_rehab_supports_request' requires clinical evidence code 'post_revision_rehab_incomplete'."
            )

    for rule in result.coverage_rules:
        if (
            rule.rule_id == "incomplete_rehab_history_supports_request"
            and "does not support" in rule.rule_text.lower()
        ):
            errors.append(
                "coverage rule 'incomplete_rehab_history_supports_request' contradicts its own rule_id semantics."
            )
        if (
            rule.rule_id == "incomplete_rehab_history_supports_request"
            and "post_revision_rehab_incomplete" in clinical_codes
            and not rule.satisfied_by
            and rule.unsatisfied_reason
        ):
            errors.append(
                "coverage rule 'incomplete_rehab_history_supports_request' should not remain unsatisfied when post_revision_rehab_incomplete evidence is present."
            )

    return errors
