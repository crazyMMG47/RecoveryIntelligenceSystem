import os

from .clinical_agent import ClinicalAgent
from .insurance_agent import InsuranceAgent
from .schemas import (
    CarePath,
    CaseData,
    CaseResolution,
    ClinicalAgentInput,
    ConflictItem,
    HandoffPacket,
    InsuranceAgentInput,
    OrchestratorInput,
    OrchestratorOutput,
    QuestionItem,
    Readiness,
    RequirementStatus,
    RunCaseResponse,
    WorkflowOwner,
    WorkflowStep,
)


class Orchestrator:
    def __init__(
        self,
        *,
        clinical_agent: object | None = None,
        insurance_agent: object | None = None,
    ) -> None:
        self.clinical_agent = clinical_agent or ClinicalAgent()
        self.insurance_agent = insurance_agent or InsuranceAgent()

    @classmethod
    def from_env(cls) -> "Orchestrator":
        use_gemini_clinical = os.getenv("USE_GEMINI_CLINICAL_AGENT", "").lower() == "true"
        if use_gemini_clinical:
            from .clinical_llm_agent import ClinicalLLMAgent
            from .gemini_llm import GeminiStructuredLLM

            clinical_agent = ClinicalLLMAgent(GeminiStructuredLLM())
        else:
            clinical_agent = ClinicalAgent()
        return cls(clinical_agent=clinical_agent)

    def build_clinical_input(self, user_question: str, case: CaseData) -> ClinicalAgentInput:
        return ClinicalAgentInput(
            question=user_question,
            patient_summary=case.patient_summary,
            clinical_notes=case.clinical_notes,
            pt_notes=case.pt_notes,
            imaging=case.imaging,
        )

    def build_insurance_input(
        self,
        user_question: str,
        case: CaseData,
        clinical_output,
    ) -> InsuranceAgentInput:
        return InsuranceAgentInput(
            question=user_question,
            policy_text=" ".join(case.policy_text),
            clinical_decision=clinical_output.decision,
            clinical_evidence=clinical_output.evidence,
            clinical_requirements=clinical_output.requirements,
        )

    def resolve_conflicts(self, orchestrator_input: OrchestratorInput) -> list[ConflictItem]:
        conflicts: list[ConflictItem] = []
        clinical_output = orchestrator_input.clinical_output
        insurance_output = orchestrator_input.insurance_output

        if clinical_output.decision.recommended_path == CarePath.ADDITIONAL_STRUCTURED_PT and insurance_output.decision.coverage_position == "likely_denied":
            conflicts.append(
                ConflictItem(
                    conflict_type="clinical_insurance_mismatch",
                    between=["clinical", "insurance"],
                    reason="Clinical path recommends additional PT while insurance position trends toward denial.",
                    blocking=True,
                )
            )
        if clinical_output.confidence.value == "low" or insurance_output.confidence.value == "low":
            conflicts.append(
                ConflictItem(
                    conflict_type="low_confidence",
                    between=["clinical", "insurance"],
                    reason="At least one agent returned low confidence.",
                    blocking=True,
                )
            )
        return conflicts

    def build_final_output(self, orchestrator_input: OrchestratorInput) -> OrchestratorOutput:
        clinical_output = orchestrator_input.clinical_output
        insurance_output = orchestrator_input.insurance_output
        conflict_items = self.resolve_conflicts(orchestrator_input)

        blocking_requirements = [
            item
            for item in clinical_output.requirements + insurance_output.requirements
            if item.status != RequirementStatus.SATISFIED
        ]
        open_questions: list[QuestionItem] = []
        clinical_requirement_codes = {item.code for item in clinical_output.requirements}
        if "objective_deficit_measurement" in clinical_requirement_codes:
            open_questions.append(
                QuestionItem(
                    code="objective_deficit_quantification",
                    question="What objective strength and functional measurements can be attached to support the PT request?",
                )
            )
        insurance_requirement_codes = {item.code for item in insurance_output.requirements}
        if "document_incomplete_rehab_course" in insurance_requirement_codes:
            open_questions.append(
                QuestionItem(
                    code="prior_rehab_gap_documentation",
                    question="What documentation proves that the prior post-revision rehabilitation course was incomplete?",
                )
            )

        readiness = Readiness.READY
        if blocking_requirements:
            readiness = Readiness.BLOCKED
        if clinical_output.decision.recommended_path == CarePath.NEED_MORE_INFORMATION:
            readiness = Readiness.NEED_MORE_INFO

        recommended_workflow = [
            WorkflowStep(
                step_id="clinical_collect_deficits",
                owner=WorkflowOwner.CLINICAL,
                action="Collect objective strength and functional movement measurements.",
                depends_on=[],
                done_definition="Objective deficit measurements are attached to the case.",
            ),
            WorkflowStep(
                step_id="clinical_define_pt_plan",
                owner=WorkflowOwner.CLINICAL,
                action="Define a structured supervised PT plan with frequency and reassessment window.",
                depends_on=["clinical_collect_deficits"],
                done_definition="A time-bounded PT plan is available for submission.",
            ),
            WorkflowStep(
                step_id="insurance_prepare_packet",
                owner=WorkflowOwner.INSURANCE,
                action="Prepare utilization review packet with physician justification and therapy plan.",
                depends_on=["clinical_collect_deficits", "clinical_define_pt_plan"],
                done_definition="Submission packet includes physician note, objective deficits, and therapy plan.",
            ),
        ]
        if conflict_items:
            recommended_workflow.append(
                WorkflowStep(
                    step_id="human_review",
                    owner=WorkflowOwner.HUMAN,
                    action="Resolve blocking conflict before submission.",
                    depends_on=["insurance_prepare_packet"],
                    done_definition="A clinician or reviewer resolves the blocking conflict.",
                )
            )

        return OrchestratorOutput(
            case_resolution=CaseResolution(
                recommended_path=clinical_output.decision.recommended_path,
                readiness=readiness,
                requires_human_review=bool(conflict_items),
            ),
            key_evidence=clinical_output.evidence,
            blocking_requirements=blocking_requirements,
            conflict_items=conflict_items,
            recommended_workflow=recommended_workflow,
            handoff_packet=HandoffPacket(
                next_consumer="downstream_llm_or_ui",
                payload_keys=[
                    "case_resolution",
                    "key_evidence",
                    "blocking_requirements",
                    "recommended_workflow",
                ],
                notes=[
                    "Generate user-facing explanation from structured fields only.",
                    "Do not invent missing documentation.",
                ],
            ),
            open_questions=open_questions,
            escalation_reason="Blocking conflict exists." if conflict_items else "",
        )

    def run(self, user_question: str, case: CaseData) -> RunCaseResponse:
        clinical_input = self.build_clinical_input(user_question, case)
        clinical_output = self.clinical_agent.run(clinical_input)

        insurance_input = self.build_insurance_input(
            user_question=user_question,
            case=case,
            clinical_output=clinical_output,
        )
        insurance_output = self.insurance_agent.run(insurance_input)

        orchestrator_input = OrchestratorInput(
            user_question=user_question,
            clinical_output=clinical_output,
            insurance_output=insurance_output,
        )
        orchestrator_output = self.build_final_output(orchestrator_input)

        return RunCaseResponse(
            clinical_input=clinical_input,
            clinical_output=clinical_output,
            insurance_input=insurance_input,
            insurance_output=insurance_output,
            orchestrator_input=orchestrator_input,
            orchestrator_output=orchestrator_output,
        )
