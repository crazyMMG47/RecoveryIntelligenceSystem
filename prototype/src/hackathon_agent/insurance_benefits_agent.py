from __future__ import annotations

from .schemas import (
    BenefitCoverageStatus,
    ConfidenceLevel,
    InsuranceBenefitsInput,
    InsuranceBenefitsOutput,
    PlanSource,
)


DEMO_PLAN_ID = "kp_wa_visitsplus_silver_4500_2026"
DEMO_PLAN_NAME = "Kaiser Foundation Health Plan of Washington VisitsPlus Silver 4500 (2026)"
DEMO_SERVICE = "Outpatient physical therapy and rehabilitation services"

DEMO_PLAN_SOURCES = [
    PlanSource(
        title="2026 VisitsPlus Silver 4500 EOC",
        url=(
            "https://healthy.kaiserpermanente.org/content/dam/kporg/final/documents/"
            "health-plan-documents/eoc/wa/individual-family/2026/"
            "off-visitsplus-silver-4500-wa-en.pdf"
        ),
        note=(
            "Official sample Evidence of Coverage for the fixed demo plan. "
            "Used for deductible, coinsurance, out-of-pocket maximum, rehab visit limits, "
            "network requirement, and outpatient rehab cost-sharing."
        ),
    ),
    PlanSource(
        title="Washington Individual & Family Plan Documents",
        url="https://healthy.kaiserpermanente.org/washington/support/forms/documents/individual-family",
        note="Official Kaiser page listing the fixed demo plan document.",
    ),
]


class InsuranceBenefitsAgent:
    def run(self, payload: InsuranceBenefitsInput) -> InsuranceBenefitsOutput:
        coverage_status = BenefitCoverageStatus.COVERED_SUBJECT_TO_PLAN_RULES
        if payload.clinical_decision.recommended_service != "supervised_pt":
            coverage_status = BenefitCoverageStatus.UNCLEAR

        return InsuranceBenefitsOutput(
            plan_id=DEMO_PLAN_ID,
            plan_name=DEMO_PLAN_NAME,
            service=DEMO_SERVICE,
            coverage_status=coverage_status,
            network_requirement=(
                "Covered services must be received from a Network Provider at a Network Facility "
                "unless preauthorized or received as emergency services."
            ),
            authorization_requirement=(
                "For the rehabilitation benefit itself, preauthorization is not required under the "
                "fixed demo plan. Coverage still depends on medical necessity, plan rules, and visit limits."
            ),
            visit_limit=(
                "Rehabilitation care is limited to a combined total of 30 inpatient days and "
                "25 outpatient visits per calendar year."
            ),
            member_cost_share=(
                "Outpatient specialty rehabilitation office visits are $75 per visit. "
                "Group occupational, physical, or speech therapy visits are one-half of the office "
                "visit copayment. All other covered rehab services are subject to 30% plan coinsurance "
                "after the deductible."
            ),
            deductible="Annual deductible is $4,500 per member or $9,000 per family unit per calendar year.",
            out_of_pocket_max=(
                "Out-of-pocket maximum is $9,800 per member or $19,600 per family unit per calendar year "
                "for covered services."
            ),
            assumptions=[
                "Demo assumes the member is enrolled in the fixed 2026 Washington VisitsPlus Silver 4500 plan.",
                "Demo assumes the requested PT is delivered in-network.",
                "Demo assumes outpatient physical therapy is being requested, not inpatient rehab or non-network care.",
                "This benefits layer estimates plan coverage rules and cost-sharing, not a finalized claims adjudication.",
            ],
            sources=DEMO_PLAN_SOURCES,
            confidence=ConfidenceLevel.HIGH,
        )
