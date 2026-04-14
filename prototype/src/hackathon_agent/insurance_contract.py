from __future__ import annotations

from .policy_retriever import RetrievedPolicyChunk
from .schemas import (
    CarePath,
    InsuranceAgentInput,
    InsuranceAgentOutput,
    RequirementStatus,
    WorkflowOwner,
)


ALLOWED_REQUIREMENT_CODES = {
    "physician_justification_note",
    "objective_functional_measurements",
    "structured_therapy_plan",
    "document_incomplete_rehab_course",
}

ALLOWED_APPEAL_RISK_CODES = {
    "attendance_interruptions_may_reduce_approval_strength",
}

ALLOWED_NEXT_STEPS = {
    "attach_physician_justification_note",
    "attach_objective_deficit_measurements",
    "attach_structured_pt_plan",
    "add_context_for_attendance_interruptions",
}

ALLOWED_DECISION_DRIVERS = {
    "physician_justification",
    "objective_functional_deficit",
    "therapy_plan",
    "incomplete_prior_rehab_supports_request",
    "clinical_path_not_pt",
    "missing_policy_support",
    "missing_required_documentation",
}

ALLOWED_COVERAGE_RULE_IDS = {
    "physician_justification_required",
    "objective_deficit_required",
    "therapy_plan_required",
    "adherence_history_review",
    "incomplete_rehab_history_supports_request",
}


def build_allowed_policy_source_refs(
    retrieved_policy: list[RetrievedPolicyChunk],
) -> list[str]:
    return [chunk.source_ref for chunk in retrieved_policy]


def validate_insurance_output(
    payload: InsuranceAgentInput,
    retrieved_policy: list[RetrievedPolicyChunk],
    result: InsuranceAgentOutput,
) -> list[str]:
    errors: list[str] = []

    allowed_policy_source_refs = set(build_allowed_policy_source_refs(retrieved_policy))
    clinical_codes = {item.code for item in payload.clinical_evidence}

    # 1. Validate decision drivers
    invalid_decision_drivers = [
        code for code in result.decision.decision_drivers
        if code not in ALLOWED_DECISION_DRIVERS
    ]
    if invalid_decision_drivers:
        errors.append(
            f"decision.decision_drivers contains unsupported values: {invalid_decision_drivers}."
        )

    # 2. Validate requirements
    for requirement in result.requirements:
        if requirement.code not in ALLOWED_REQUIREMENT_CODES:
            errors.append(
                f"requirement.code '{requirement.code}' is not in the allowed insurance vocabulary."
            )
        if requirement.owner != WorkflowOwner.INSURANCE:
            errors.append(
                f"requirement.owner for '{requirement.code}' must be 'insurance'."
            )

    # 3. Validate appeal risk factors
    for risk_item in result.appeal_risk_factors:
        if risk_item.code not in ALLOWED_APPEAL_RISK_CODES:
            errors.append(
                f"appeal_risk_factors.code '{risk_item.code}' is not in the allowed insurance vocabulary."
            )

    # 4. Validate next steps
    invalid_next_steps = [
        step for step in result.next_steps
        if step not in ALLOWED_NEXT_STEPS
    ]
    if invalid_next_steps:
        errors.append(f"next_steps contains unsupported values: {invalid_next_steps}.")

    # 5. Validate coverage rules
    for rule in result.coverage_rules:
        if rule.rule_id not in ALLOWED_COVERAGE_RULE_IDS:
            errors.append(
                f"coverage_rules.rule_id '{rule.rule_id}' is not in the allowed insurance vocabulary."
            )
        if not rule.rule_text.strip():
            errors.append(f"coverage rule '{rule.rule_id}' must include non-empty rule_text.")
        if not rule.effect.strip():
            errors.append(f"coverage rule '{rule.rule_id}' must include non-empty effect.")

    # 6. If no retrieved policy exists, result should not pretend strong confidence
    if not allowed_policy_source_refs and result.confidence.value == "high":
        errors.append(
            "high confidence is not allowed when no retrieved policy text is available."
        )

    # 7. If clinical path is not additional structured PT, do not claim likely_covered
    if (
        payload.clinical_decision.recommended_path != CarePath.ADDITIONAL_STRUCTURED_PT
        and result.decision.coverage_position.value == "likely_covered"
    ):
        errors.append(
            "coverage_position cannot be likely_covered when the clinical path is not additional_structured_pt."
        )

    # 8. If likely_covered, major documentation requirements should not remain unsatisfied
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

    # 9. If the LLM says physician justification is a driver, it should usually be reflected
    # in either a rule match or a requirement.
    if "physician_justification" in result.decision.decision_drivers:
        has_physician_signal = any(
            rule.rule_id == "physician_justification_required"
            for rule in result.coverage_rules
        ) or any(
            requirement.code == "physician_justification_note"
            for requirement in result.requirements
        )
        if not has_physician_signal:
            errors.append(
                "decision driver 'physician_justification' requires a matching rule or requirement."
            )

    # 10. If the LLM says objective functional deficit is a driver, it should connect to either
    # policy rules or the clinical evidence.
    if "objective_functional_deficit" in result.decision.decision_drivers:
        has_objective_rule = any(
            rule.rule_id == "objective_deficit_required"
            for rule in result.coverage_rules
        )
        has_objective_clinical_support = bool(
            {"documented_quadriceps_weakness", "documented_neuromuscular_deficit"} & clinical_codes
        )
        if not (has_objective_rule or has_objective_clinical_support):
            errors.append(
                "decision driver 'objective_functional_deficit' is unsupported by policy rule or clinical evidence."
            )

    # 11. If therapy plan is a driver, a related rule or requirement should exist
    if "therapy_plan" in result.decision.decision_drivers:
        has_therapy_plan_signal = any(
            rule.rule_id == "therapy_plan_required"
            for rule in result.coverage_rules
        ) or any(
            requirement.code == "structured_therapy_plan"
            for requirement in result.requirements
        )
        if not has_therapy_plan_signal:
            errors.append(
                "decision driver 'therapy_plan' requires a matching rule or requirement."
            )

    # 12. If incomplete prior rehab is used as a driver, it should be grounded in clinical evidence
    if "incomplete_prior_rehab_supports_request" in result.decision.decision_drivers:
        if "post_revision_rehab_incomplete" not in clinical_codes:
            errors.append(
                "decision driver 'incomplete_prior_rehab_supports_request' requires clinical evidence code 'post_revision_rehab_incomplete'."
            )

    return errors