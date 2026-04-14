import os

from .clinical_agent import ClinicalAgent
from .insurance_agent import InsuranceAgent
from .schemas import (
    CarePath,
    CaseData,
    CaseResolution,
    ClinicalAgentInput,
    ConfidenceLevel,
    ConflictItem,
    CoverageDecision,
    HandoffPacket,
    InsuranceAgentInput,
    OrchestratorInput,
    OrchestratorOutput,
    QuestionItem,
    Readiness,
    RequirementItem,
    RequirementStatus,
    RunCaseResponse,
    WorkflowOwner,
    WorkflowStep,
)


class Orchestrator:
    """
    Coordinates the end-to-end workflow across agents.

    Responsibilities:
    1. Build agent-specific inputs from raw case data
    2. Run clinical agent first, then insurance agent
    3. Detect conflicts / blockers / missing information
    4. Build a case-level workflow and final orchestrated output
    """

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
        use_gemini_insurance = os.getenv("USE_GEMINI_INSURANCE_AGENT", "").lower() == "true"

        if use_gemini_clinical:
            from .clinical_llm_agent import ClinicalLLMAgent
            from .gemini_llm import GeminiStructuredLLM
            clinical_agent = ClinicalLLMAgent(GeminiStructuredLLM())
        else:
            clinical_agent = ClinicalAgent()

        if use_gemini_insurance:
            from .gemini_llm import GeminiStructuredLLM
            from .insurance_llm_agent import InsuranceLLMAgent
            from .policy_retriever import PolicyRetriever

            insurance_agent = InsuranceLLMAgent(
                llm=GeminiStructuredLLM(),
                retriever=PolicyRetriever(),
            )
        else:
            insurance_agent = InsuranceAgent()

        return cls(
            clinical_agent=clinical_agent,
            insurance_agent=insurance_agent,
        )

    def build_clinical_input(self, user_question: str, case: CaseData) -> ClinicalAgentInput:
        """
        Build the raw clinical input package from the case.
        """
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
        """
        Build the insurance input package using:
        - the original user question
        - policy text
        - the structured output from the clinical agent
        """
        return InsuranceAgentInput(
            question=user_question,
            policy_text=" ".join(case.policy_text),
            clinical_decision=clinical_output.decision,
            clinical_evidence=clinical_output.evidence,
            clinical_requirements=clinical_output.requirements,
        )

    def detect_conflicts(self, orchestrator_input: OrchestratorInput) -> list[ConflictItem]:
        """
        Detect major case-level conflicts that should block automatic progression.
        This does not "fix" the conflict; it records it so the orchestrator can
        choose a safer next step.
        """
        conflicts: list[ConflictItem] = []
        clinical_output = orchestrator_input.clinical_output
        insurance_output = orchestrator_input.insurance_output

        # Conflict 1:
        # Clinical path says additional structured PT is appropriate,
        # but insurance trends toward denial.
        if (
            clinical_output.decision.recommended_path == CarePath.ADDITIONAL_STRUCTURED_PT
            and insurance_output.decision.coverage_position == CoverageDecision.LIKELY_DENIED
        ):
            conflicts.append(
                ConflictItem(
                    conflict_type="clinical_insurance_mismatch",
                    between=["clinical", "insurance"],
                    reason=(
                        "Clinical recommends additional structured PT while insurance "
                        "position trends toward denial."
                    ),
                    blocking=True,
                )
            )

        # Conflict 2:
        # Clinical side is too uncertain for automatic progression.
        if clinical_output.confidence == ConfidenceLevel.LOW:
            conflicts.append(
                ConflictItem(
                    conflict_type="low_clinical_confidence",
                    between=["clinical", "orchestrator"],
                    reason="Clinical output has low confidence and should not drive automatic progression.",
                    blocking=True,
                )
            )

        # Conflict 3:
        # Insurance side is too uncertain for automatic progression.
        if insurance_output.confidence == ConfidenceLevel.LOW:
            conflicts.append(
                ConflictItem(
                    conflict_type="low_insurance_confidence",
                    between=["insurance", "orchestrator"],
                    reason="Insurance output has low confidence and should not drive automatic progression.",
                    blocking=True,
                )
            )

        # Conflict 4:
        # Clinical side explicitly says there is not enough information yet.
        if clinical_output.decision.recommended_path == CarePath.NEED_MORE_INFORMATION:
            conflicts.append(
                ConflictItem(
                    conflict_type="insufficient_clinical_information",
                    between=["clinical", "orchestrator"],
                    reason="Clinical agent indicates more information is needed before choosing a reliable care path.",
                    blocking=True,
                )
            )

        # Conflict 5:
        # Clinical output has no evidence at all.
        if not clinical_output.evidence:
            conflicts.append(
                ConflictItem(
                    conflict_type="missing_supporting_evidence",
                    between=["clinical", "orchestrator"],
                    reason="Clinical recommendation lacks supporting structured evidence.",
                    blocking=True,
                )
            )

        return conflicts

    def collect_blocking_requirements(self, orchestrator_input: OrchestratorInput) -> list[RequirementItem]:
        """
        Collect all unsatisfied or unknown requirements from both agents.
        These are the actionable blockers in the case.
        """
        clinical_output = orchestrator_input.clinical_output
        insurance_output = orchestrator_input.insurance_output

        return [
            item
            for item in (clinical_output.requirements + insurance_output.requirements)
            if item.status != RequirementStatus.SATISFIED
        ]

    def collect_open_questions(self, orchestrator_input: OrchestratorInput) -> list[QuestionItem]:
        """
        Convert important missing requirements into human-readable questions.
        """
        questions: list[QuestionItem] = []
        clinical_output = orchestrator_input.clinical_output
        insurance_output = orchestrator_input.insurance_output

        clinical_requirement_codes = {
            item.code
            for item in clinical_output.requirements
            if item.status != RequirementStatus.SATISFIED
        }
        insurance_requirement_codes = {
            item.code
            for item in insurance_output.requirements
            if item.status != RequirementStatus.SATISFIED
        }

        if "objective_deficit_measurement" in clinical_requirement_codes:
            questions.append(
                QuestionItem(
                    code="objective_deficit_quantification",
                    question="What objective strength and functional measurements can be attached to support the PT request?",
                )
            )

        if "document_prior_rehab_gap" in clinical_requirement_codes:
            questions.append(
                QuestionItem(
                    code="prior_rehab_gap_clinical_documentation",
                    question="What clinical documentation shows that the prior rehabilitation course was incomplete?",
                )
            )

        if "document_incomplete_rehab_course" in insurance_requirement_codes:
            questions.append(
                QuestionItem(
                    code="prior_rehab_gap_insurance_documentation",
                    question="What documentation proves that the prior post-revision rehabilitation course was incomplete?",
                )
            )

        if "objective_functional_measurements" in insurance_requirement_codes:
            questions.append(
                QuestionItem(
                    code="insurance_objective_measurements",
                    question="Which measurable strength or movement deficits can be submitted for utilization review?",
                )
            )

        if "physician_justification_note" in insurance_requirement_codes:
            questions.append(
                QuestionItem(
                    code="physician_justification_needed",
                    question="Can a physician note be attached to justify the requested PT frequency and medical necessity?",
                )
            )

        if "structured_therapy_plan" in insurance_requirement_codes:
            questions.append(
                QuestionItem(
                    code="therapy_plan_needed",
                    question="Can a structured PT plan with goals, frequency, and reassessment timing be attached?",
                )
            )

        return questions

    def determine_readiness(
        self,
        orchestrator_input: OrchestratorInput,
        conflict_items: list[ConflictItem],
        blocking_requirements: list[RequirementItem],
    ) -> Readiness:
        """
        Convert the current case state into an overall readiness signal.
        """
        clinical_output = orchestrator_input.clinical_output

        if clinical_output.decision.recommended_path == CarePath.NEED_MORE_INFORMATION:
            return Readiness.NEED_MORE_INFO

        if any(item.blocking for item in conflict_items):
            return Readiness.BLOCKED

        if blocking_requirements:
            return Readiness.BLOCKED

        return Readiness.READY

    def build_recommended_workflow(
        self,
        orchestrator_input: OrchestratorInput,
        conflict_items: list[ConflictItem],
    ) -> list[WorkflowStep]:
        """
        Build a dynamic workflow based on actual unsatisfied requirements
        and the current recommended path.
        """
        workflow: list[WorkflowStep] = []
        clinical_output = orchestrator_input.clinical_output
        insurance_output = orchestrator_input.insurance_output

        clinical_missing = {
            item.code
            for item in clinical_output.requirements
            if item.status != RequirementStatus.SATISFIED
        }
        insurance_missing = {
            item.code
            for item in insurance_output.requirements
            if item.status != RequirementStatus.SATISFIED
        }

        # Branch workflow based on the clinical path.
        if clinical_output.decision.recommended_path == CarePath.SURGICAL_REEVALUATION:
            workflow.append(
                WorkflowStep(
                    step_id="clinical_surgical_reevaluation",
                    owner=WorkflowOwner.CLINICAL,
                    action="Arrange surgical reevaluation based on the current clinical and imaging findings.",
                    depends_on=[],
                    done_definition="A clinician reviews the case for possible structural failure and next surgical steps.",
                )
            )

        elif clinical_output.decision.recommended_path == CarePath.NEED_MORE_INFORMATION:
            workflow.append(
                WorkflowStep(
                    step_id="clinical_collect_missing_information",
                    owner=WorkflowOwner.CLINICAL,
                    action="Collect additional clinical information before a final care path is chosen.",
                    depends_on=[],
                    done_definition="Missing clinical information is attached and the case is ready for reassessment.",
                )
            )

        else:
            # PT-oriented workflow
            if "objective_deficit_measurement" in clinical_missing or "objective_functional_measurements" in insurance_missing:
                workflow.append(
                    WorkflowStep(
                        step_id="clinical_collect_deficits",
                        owner=WorkflowOwner.CLINICAL,
                        action="Collect objective strength and functional movement measurements.",
                        depends_on=[],
                        done_definition="Objective deficit measurements are attached to the case.",
                    )
                )

            if "document_prior_rehab_gap" in clinical_missing or "document_incomplete_rehab_course" in insurance_missing:
                workflow.append(
                    WorkflowStep(
                        step_id="clinical_document_rehab_gap",
                        owner=WorkflowOwner.CLINICAL,
                        action="Document that the prior post-revision rehabilitation course was incomplete.",
                        depends_on=[],
                        done_definition="The case clearly documents the incomplete prior rehabilitation course.",
                    )
                )

            if "structured_therapy_plan" in insurance_missing:
                workflow.append(
                    WorkflowStep(
                        step_id="clinical_define_pt_plan",
                        owner=WorkflowOwner.CLINICAL,
                        action="Define a structured supervised PT plan with goals, frequency, and reassessment window.",
                        depends_on=[
                            step.step_id
                            for step in workflow
                            if step.owner == WorkflowOwner.CLINICAL
                        ],
                        done_definition="A structured PT plan is available for submission.",
                    )
                )

            if "physician_justification_note" in insurance_missing:
                workflow.append(
                    WorkflowStep(
                        step_id="insurance_prepare_packet",
                        owner=WorkflowOwner.INSURANCE,
                        action="Prepare the utilization review packet with physician justification and supporting documentation.",
                        depends_on=[step.step_id for step in workflow],
                        done_definition="The submission packet includes physician justification and required supporting documents.",
                    )
                )

        # Human review is appended only if unresolved blocking conflicts remain.
        if any(item.blocking for item in conflict_items):
            workflow.append(
                WorkflowStep(
                    step_id="human_review",
                    owner=WorkflowOwner.HUMAN,
                    action="Review unresolved conflict or low-confidence case before further progression.",
                    depends_on=[step.step_id for step in workflow],
                    done_definition="A clinician or reviewer decides whether the case can proceed safely.",
                )
            )

        return workflow

    def build_handoff_packet(self, recommended_workflow: list[WorkflowStep]) -> HandoffPacket:
        """
        Build a compact packet for the next system or UI layer.
        """
        payload_keys = [
            "case_resolution",
            "key_evidence",
            "blocking_requirements",
            "recommended_workflow",
            "open_questions",
        ]

        if any(step.step_id == "human_review" for step in recommended_workflow):
            payload_keys.append("conflict_items")

        return HandoffPacket(
            next_consumer="downstream_llm_or_ui",
            payload_keys=payload_keys,
            notes=[
                "Generate user-facing explanation from structured fields only.",
                "Do not invent missing documentation.",
                "Escalate to human review when blocking conflicts remain unresolved.",
            ],
        )

    def build_final_output(self, orchestrator_input: OrchestratorInput) -> OrchestratorOutput:
        """
        Merge all agent outputs into a final case-level orchestration result.
        """
        clinical_output = orchestrator_input.clinical_output

        conflict_items = self.detect_conflicts(orchestrator_input)
        blocking_requirements = self.collect_blocking_requirements(orchestrator_input)
        open_questions = self.collect_open_questions(orchestrator_input)
        readiness = self.determine_readiness(
            orchestrator_input=orchestrator_input,
            conflict_items=conflict_items,
            blocking_requirements=blocking_requirements,
        )
        recommended_workflow = self.build_recommended_workflow(
            orchestrator_input=orchestrator_input,
            conflict_items=conflict_items,
        )
        handoff_packet = self.build_handoff_packet(recommended_workflow)

        return OrchestratorOutput(
            case_resolution=CaseResolution(
                recommended_path=clinical_output.decision.recommended_path,
                readiness=readiness,
                requires_human_review=any(item.blocking for item in conflict_items),
            ),
            key_evidence=clinical_output.evidence,
            blocking_requirements=blocking_requirements,
            conflict_items=conflict_items,
            recommended_workflow=recommended_workflow,
            handoff_packet=handoff_packet,
            open_questions=open_questions,
            escalation_reason=(
                "Blocking conflict exists and requires human review."
                if any(item.blocking for item in conflict_items)
                else ""
            ),
        )

    def run(self, user_question: str, case: CaseData) -> RunCaseResponse:
        """
        Execute the full workflow:
        clinical -> insurance -> orchestration.
        """
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