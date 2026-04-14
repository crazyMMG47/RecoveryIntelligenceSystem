from .schemas import (
    CarePath,
    ConfidenceLevel,
    CoverageDecision,
    EvidenceStrength,
    InsuranceAgentInput,
    InsuranceAgentOutput,
    InsuranceDecision,
    PolicyRuleMatch,
    RequirementItem,
    RequirementStatus,
    RiskItem,
    WorkflowOwner,
)


class InsuranceAgent:
    def run(self, payload: InsuranceAgentInput) -> InsuranceAgentOutput:
        coverage_rules: list[PolicyRuleMatch] = []
        requirements: list[RequirementItem] = []
        appeal_risk_factors: list[RiskItem] = []
        next_steps: list[str] = []
        decision_drivers: list[str] = []

        policy_text = payload.policy_text.lower()
        clinical_codes = {item.code for item in payload.clinical_evidence}

        if "physician justification" in policy_text:
            coverage_rules.append(
                PolicyRuleMatch(
                    rule_id="physician_justification_required",
                    rule_text="Higher-frequency PT requires physician justification.",
                    effect="supporting_if_satisfied",
                    satisfied_by=["clinical_request_with_physician_note"] if payload.clinical_decision.recommended_service == "supervised_pt" else [],
                    unsatisfied_reason="" if payload.clinical_decision.recommended_service == "supervised_pt" else "no_pt_request_recommended",
                )
            )
            requirements.append(
                RequirementItem(
                    code="physician_justification_note",
                    description="Physician note requesting 2x/week PT is required.",
                    owner=WorkflowOwner.INSURANCE,
                    status=RequirementStatus.UNSATISFIED,
                )
            )
            decision_drivers.append("physician_justification")

        if "measurable functional deficits" in policy_text:
            coverage_rules.append(
                PolicyRuleMatch(
                    rule_id="objective_deficit_required",
                    rule_text="Extended PT requests should document measurable functional deficits.",
                    effect="supporting_if_satisfied",
                    satisfied_by=["documented_quadriceps_weakness", "documented_neuromuscular_deficit"],
                    unsatisfied_reason="missing_objective_measurements",
                )
            )
            requirements.append(
                RequirementItem(
                    code="objective_functional_measurements",
                    description="Objective strength and movement deficit measurements are needed for utilization review.",
                    owner=WorkflowOwner.INSURANCE,
                    status=RequirementStatus.UNSATISFIED,
                )
            )
            decision_drivers.append("objective_functional_deficit")

        if "clear therapy plan" in policy_text:
            coverage_rules.append(
                PolicyRuleMatch(
                    rule_id="therapy_plan_required",
                    rule_text="A clear therapy plan is required.",
                    effect="supporting_if_satisfied",
                    satisfied_by=[],
                    unsatisfied_reason="therapy_plan_not_yet_attached",
                )
            )
            requirements.append(
                RequirementItem(
                    code="structured_therapy_plan",
                    description="Structured PT plan with goals, frequency, and reassessment timing is required.",
                    owner=WorkflowOwner.INSURANCE,
                    status=RequirementStatus.UNSATISFIED,
                )
            )
            decision_drivers.append("therapy_plan")

        if "adherence history" in policy_text:
            appeal_risk_factors.append(
                RiskItem(
                    code="attendance_interruptions_may_reduce_approval_strength",
                    description="Interrupted attendance may weaken approval unless contextualized.",
                    severity=EvidenceStrength.MODERATE,
                )
            )

        if "post_revision_rehab_incomplete" in clinical_codes:
            decision_drivers.append("incomplete_prior_rehab_supports_request")
        else:
            requirements.append(
                RequirementItem(
                    code="document_incomplete_rehab_course",
                    description="Need documentation that the prior structured rehab course was incomplete.",
                    owner=WorkflowOwner.INSURANCE,
                    status=RequirementStatus.UNSATISFIED,
                )
            )

        next_steps.extend(
            [
                "attach_physician_justification_note",
                "attach_objective_deficit_measurements",
                "attach_structured_pt_plan",
            ]
        )
        if appeal_risk_factors:
            next_steps.append("add_context_for_attendance_interruptions")

        unresolved = [item for item in requirements if item.status != RequirementStatus.SATISFIED]
        if payload.clinical_decision.recommended_path != CarePath.ADDITIONAL_STRUCTURED_PT:
            coverage_position = CoverageDecision.UNCLEAR
        elif unresolved:
            coverage_position = CoverageDecision.UNCLEAR
        else:
            coverage_position = CoverageDecision.LIKELY_COVERED

        return InsuranceAgentOutput(
            decision=InsuranceDecision(
                coverage_position=coverage_position,
                review_needed=True,
                decision_drivers=sorted(set(decision_drivers)),
            ),
            coverage_rules=coverage_rules,
            requirements=requirements,
            appeal_risk_factors=appeal_risk_factors,
            next_steps=sorted(set(next_steps)),
            confidence=ConfidenceLevel.MEDIUM if coverage_position == CoverageDecision.UNCLEAR else ConfidenceLevel.HIGH,
        )
