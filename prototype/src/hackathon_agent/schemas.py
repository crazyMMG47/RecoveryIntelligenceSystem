from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CoverageDecision(str, Enum):
    LIKELY_COVERED = "likely_covered"
    LIKELY_DENIED = "likely_denied"
    UNCLEAR = "unclear"


class BenefitCoverageStatus(str, Enum):
    COVERED_SUBJECT_TO_PLAN_RULES = "covered_subject_to_plan_rules"
    NOT_COVERED = "not_covered"
    UNCLEAR = "unclear"


class CarePath(str, Enum):
    ADDITIONAL_STRUCTURED_PT = "additional_structured_pt"
    SURGICAL_REEVALUATION = "surgical_reevaluation"
    NEED_MORE_INFORMATION = "need_more_information"


class RecommendationDisposition(str, Enum):
    RECOMMEND = "recommend"
    DO_NOT_RECOMMEND = "do_not_recommend"
    CONSIDER_AFTER_PREREQUISITES = "consider_after_prerequisites"


class EvidenceStrength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


class SourceType(str, Enum):
    PATIENT_SUMMARY = "patient_summary"
    CLINICAL_NOTE = "clinical_note"
    PT_NOTE = "pt_note"
    IMAGING = "imaging"
    POLICY = "policy"
    ORCHESTRATOR = "orchestrator"


class RequirementStatus(str, Enum):
    SATISFIED = "satisfied"
    UNSATISFIED = "unsatisfied"
    UNKNOWN = "unknown"


class WorkflowOwner(str, Enum):
    CLINICAL = "clinical"
    INSURANCE = "insurance"
    ORCHESTRATOR = "orchestrator"
    HUMAN = "human"


class Readiness(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"
    NEED_MORE_INFO = "need_more_info"


class EvidenceItem(StrictModel):
    code: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    source_type: SourceType
    source_ref: str = Field(min_length=1)
    supports: str = Field(min_length=1)
    strength: EvidenceStrength


class RequirementItem(StrictModel):
    code: str = Field(min_length=1)
    description: str = Field(min_length=1)
    owner: WorkflowOwner
    status: RequirementStatus


class RiskItem(StrictModel):
    code: str = Field(min_length=1)
    description: str = Field(min_length=1)
    severity: EvidenceStrength


class PolicyRuleMatch(StrictModel):
    rule_id: str = Field(min_length=1)
    rule_text: str = Field(min_length=1)
    effect: str = Field(min_length=1)
    satisfied_by: list[str] = Field(default_factory=list)
    unsatisfied_reason: str = ""


class ConflictItem(StrictModel):
    conflict_type: str = Field(min_length=1)
    between: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)
    blocking: bool


class WorkflowStep(StrictModel):
    step_id: str = Field(min_length=1)
    owner: WorkflowOwner
    action: str = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list)
    done_definition: str = Field(min_length=1)


class QuestionItem(StrictModel):
    code: str = Field(min_length=1)
    question: str = Field(min_length=1)


class HandoffPacket(StrictModel):
    next_consumer: str = Field(min_length=1)
    payload_keys: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ClinicalDecision(StrictModel):
    recommended_service: str = Field(min_length=1)
    recommendation_disposition: RecommendationDisposition
    recommended_path: CarePath
    recommendation_reason_codes: list[str] = Field(default_factory=list)


class InsuranceDecision(StrictModel):
    coverage_position: CoverageDecision
    review_needed: bool
    decision_drivers: list[str] = Field(default_factory=list)


class PlanSource(StrictModel):
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    note: str = Field(min_length=1)


class InsuranceBenefitsInput(StrictModel):
    question: str = Field(min_length=1)
    clinical_decision: ClinicalDecision
    clinical_evidence: list[EvidenceItem] = Field(default_factory=list)


class InsuranceBenefitsOutput(StrictModel):
    plan_id: str = Field(min_length=1)
    plan_name: str = Field(min_length=1)
    service: str = Field(min_length=1)
    coverage_status: BenefitCoverageStatus
    network_requirement: str = Field(min_length=1)
    authorization_requirement: str = Field(min_length=1)
    visit_limit: str = Field(min_length=1)
    member_cost_share: str = Field(min_length=1)
    deductible: str = Field(min_length=1)
    out_of_pocket_max: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    sources: list[PlanSource] = Field(default_factory=list)
    confidence: ConfidenceLevel


class CaseResolution(StrictModel):
    recommended_path: CarePath
    readiness: Readiness
    requires_human_review: bool


class ClinicalAgentInput(StrictModel):
    question: str = Field(min_length=1)
    patient_summary: str = Field(min_length=1)
    clinical_notes: list[str] = Field(min_length=1)
    pt_notes: list[str] = Field(min_length=1)
    imaging: list[str] = Field(min_length=1)


class ClinicalAgentOutput(StrictModel):
    decision: ClinicalDecision
    evidence: list[EvidenceItem] = Field(default_factory=list)
    requirements: list[RequirementItem] = Field(default_factory=list)
    risk_items: list[RiskItem] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel


class InsuranceAgentInput(StrictModel):
    question: str = Field(min_length=1)
    clinical_decision: ClinicalDecision
    clinical_evidence: list[EvidenceItem] = Field(default_factory=list)
    clinical_requirements: list[RequirementItem] = Field(default_factory=list)


class InsuranceAgentOutput(StrictModel):
    decision: InsuranceDecision
    coverage_rules: list[PolicyRuleMatch] = Field(default_factory=list)
    requirements: list[RequirementItem] = Field(default_factory=list)
    appeal_risk_factors: list[RiskItem] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel


class OrchestratorInput(StrictModel):
    user_question: str = Field(min_length=1)
    clinical_output: ClinicalAgentOutput
    insurance_output: InsuranceAgentOutput
    insurance_benefits_output: InsuranceBenefitsOutput


class OrchestratorOutput(StrictModel):
    case_resolution: CaseResolution
    key_evidence: list[EvidenceItem] = Field(default_factory=list)
    blocking_requirements: list[RequirementItem] = Field(default_factory=list)
    benefits_summary: list[str] = Field(default_factory=list)
    conflict_items: list[ConflictItem] = Field(default_factory=list)
    recommended_workflow: list[WorkflowStep] = Field(default_factory=list)
    handoff_packet: HandoffPacket
    open_questions: list[QuestionItem] = Field(default_factory=list)
    escalation_reason: str = ""


class ExternalAnswerSection(StrictModel):
    topic: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    confidence: ConfidenceLevel
    supporting_points: list[str] = Field(default_factory=list)
    supporting_evidence_refs: list[str] = Field(default_factory=list)


class ExternalAgentResponse(StrictModel):
    case_id: str = Field(min_length=1)
    user_question: str = Field(min_length=1)
    short_answer: str = Field(min_length=1)
    readiness: Readiness
    requires_human_review: bool
    sections: list[ExternalAnswerSection] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    blocking_items: list[str] = Field(default_factory=list)
    benefits_at_a_glance: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class CaseData(StrictModel):
    case_id: str = Field(min_length=1)
    patient_summary: str = Field(min_length=1)
    clinical_notes: list[str] = Field(min_length=1)
    pt_notes: list[str] = Field(min_length=1)
    imaging: list[str] = Field(min_length=1)


class RunCaseRequest(StrictModel):
    user_question: str = Field(min_length=1)
    case: CaseData


class RunCaseDebugResponse(StrictModel):
    clinical_input: ClinicalAgentInput
    clinical_output: ClinicalAgentOutput
    insurance_input: InsuranceAgentInput
    insurance_output: InsuranceAgentOutput
    insurance_benefits_input: InsuranceBenefitsInput
    insurance_benefits_output: InsuranceBenefitsOutput
    orchestrator_input: OrchestratorInput
    orchestrator_output: OrchestratorOutput
