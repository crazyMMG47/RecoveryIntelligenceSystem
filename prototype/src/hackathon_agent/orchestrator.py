from .clinical_llm_agent import ClinicalLLMAgent
from .gemini_llm import GeminiStructuredLLM
from .insurance_benefits_agent import InsuranceBenefitsAgent
from .insurance_llm_agent import InsuranceLLMAgent
from .insurance_retriever import InsurancePolicyRetriever
from .schemas import (
    CarePath,
    CaseData,
    CaseResolution,
    ClinicalAgentInput,
    ConflictItem,
    ExternalAgentResponse,
    ExternalAnswerSection,
    HandoffPacket,
    InsuranceAgentInput,
    InsuranceBenefitsInput,
    OrchestratorInput,
    OrchestratorOutput,
    QuestionItem,
    Readiness,
    RequirementItem,
    RequirementStatus,
    RunCaseDebugResponse,
    WorkflowOwner,
    WorkflowStep,
)


class Orchestrator:
    def __init__(
        self,
        *,
        clinical_agent: ClinicalLLMAgent,
        insurance_agent: InsuranceLLMAgent,
        insurance_benefits_agent: InsuranceBenefitsAgent,
    ) -> None:
        self.clinical_agent = clinical_agent
        self.insurance_agent = insurance_agent
        self.insurance_benefits_agent = insurance_benefits_agent

    @classmethod
    def from_env(cls) -> "Orchestrator":
        llm = GeminiStructuredLLM()

        return cls(
            clinical_agent=ClinicalLLMAgent(llm),
            insurance_agent=InsuranceLLMAgent(
                llm=llm,
                retriever=InsurancePolicyRetriever(),
            ),
            insurance_benefits_agent=InsuranceBenefitsAgent(),
        )

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
        clinical_output,
    ) -> InsuranceAgentInput:
        return InsuranceAgentInput(
            question=user_question,
            clinical_decision=clinical_output.decision,
            clinical_evidence=clinical_output.evidence,
            clinical_requirements=clinical_output.requirements,
        )

    def build_insurance_benefits_input(
        self,
        user_question: str,
        clinical_output,
    ) -> InsuranceBenefitsInput:
        return InsuranceBenefitsInput(
            question=user_question,
            clinical_decision=clinical_output.decision,
            clinical_evidence=clinical_output.evidence,
        )

    def resolve_conflicts(self, orchestrator_input: OrchestratorInput) -> list[ConflictItem]:
        conflicts: list[ConflictItem] = []
        clinical_output = orchestrator_input.clinical_output
        insurance_output = orchestrator_input.insurance_output
        benefits_output = orchestrator_input.insurance_benefits_output

        if clinical_output.decision.recommended_path == CarePath.ADDITIONAL_STRUCTURED_PT and insurance_output.decision.coverage_position == "likely_denied":
            conflicts.append(
                ConflictItem(
                    conflict_type="clinical_insurance_mismatch",
                    between=["clinical", "insurance"],
                    reason="Clinical path recommends additional PT while insurance position trends toward denial.",
                    blocking=True,
                )
            )
        if benefits_output.coverage_status == "not_covered":
            conflicts.append(
                ConflictItem(
                    conflict_type="benefit_exclusion",
                    between=["insurance", "plan_benefits"],
                    reason="The fixed demo plan does not treat the requested service as a covered benefit.",
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

    def _dedupe_blocking_requirements(
        self,
        requirements: list[RequirementItem],
    ) -> list[RequirementItem]:
        canonical_map = {
            "document_prior_rehab_gap": "prior_rehab_gap",
            "document_incomplete_rehab_course": "prior_rehab_gap",
            "objective_deficit_measurement": "objective_measurements",
            "objective_functional_measurements": "objective_measurements",
            "structured_pt_plan_definition": "structured_pt_plan",
            "structured_therapy_plan": "structured_pt_plan",
        }

        deduped: list[RequirementItem] = []
        seen: set[str] = set()
        for requirement in requirements:
            key = canonical_map.get(requirement.code, requirement.code)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(requirement)
        return deduped

    def build_final_output(self, orchestrator_input: OrchestratorInput) -> OrchestratorOutput:
        clinical_output = orchestrator_input.clinical_output
        insurance_output = orchestrator_input.insurance_output
        benefits_output = orchestrator_input.insurance_benefits_output
        conflict_items = self.resolve_conflicts(orchestrator_input)

        raw_blocking_requirements = [
            item
            for item in clinical_output.requirements + insurance_output.requirements
            if item.status != RequirementStatus.SATISFIED
        ]
        blocking_requirements = self._dedupe_blocking_requirements(raw_blocking_requirements)
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

        benefits_summary = [
            f"Fixed demo plan: {benefits_output.plan_name}.",
            f"Benefit coverage status: {benefits_output.coverage_status.value}.",
            benefits_output.authorization_requirement,
            benefits_output.visit_limit,
            benefits_output.member_cost_share,
            benefits_output.deductible,
            benefits_output.out_of_pocket_max,
        ]

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
            benefits_summary=benefits_summary,
            conflict_items=conflict_items,
            recommended_workflow=recommended_workflow,
            handoff_packet=HandoffPacket(
                next_consumer="prompt_opinion_agent",
                payload_keys=[
                    "case_resolution",
                    "key_evidence",
                    "blocking_requirements",
                    "benefits_summary",
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

    def _confidence_rank(self, confidence: str) -> int:
        return {
            "low": 0,
            "medium": 1,
            "high": 2,
        }[confidence]

    def _min_confidence(self, *levels: str) -> str:
        return min(levels, key=self._confidence_rank)

    def _topic_confidence(self, *levels: str):
        from .schemas import ConfidenceLevel

        return ConfidenceLevel(self._min_confidence(*levels))

    def _supporting_evidence_refs(self, orchestrator_input: OrchestratorInput) -> list[str]:
        refs = [item.source_ref for item in orchestrator_input.clinical_output.evidence[:3]]
        refs.extend(
            f"policy_rule:{rule.rule_id}"
            for rule in orchestrator_input.insurance_output.coverage_rules[:2]
        )
        deduped: list[str] = []
        seen: set[str] = set()
        for ref in refs:
            if ref in seen:
                continue
            seen.add(ref)
            deduped.append(ref)
        return deduped

    def _format_requirement_list(self, requirements: list[RequirementItem]) -> list[str]:
        return [item.description for item in requirements if item.status != RequirementStatus.SATISFIED]

    def _dedupe_strings(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        return deduped

    def _build_external_response(
        self,
        *,
        case: CaseData,
        user_question: str,
        orchestrator_input: OrchestratorInput,
        orchestrator_output: OrchestratorOutput,
    ) -> ExternalAgentResponse:
        clinical_output = orchestrator_input.clinical_output
        insurance_output = orchestrator_input.insurance_output
        benefits_output = orchestrator_input.insurance_benefits_output
        blocking_items = self._format_requirement_list(orchestrator_output.blocking_requirements)
        blocking_items.extend(item.reason for item in orchestrator_output.conflict_items)
        blocking_items = self._dedupe_strings(blocking_items)

        eligibility_points = [
            f"Authorization signal: {insurance_output.decision.coverage_position.value}.",
            f"Benefit signal: {benefits_output.coverage_status.value}.",
        ]
        if blocking_items:
            eligibility_points.append(
                "Open blockers remain before a clean approval packet can be submitted."
            )

        if benefits_output.coverage_status.value == "not_covered":
            eligibility_answer = (
                "Under the fixed demo plan assumptions, this request does not currently look covered."
            )
        elif insurance_output.decision.coverage_position.value == "likely_denied":
            eligibility_answer = (
                "With the current packet, approval for additional 2x/week supervised PT looks unlikely."
            )
        elif blocking_items:
            eligibility_answer = (
                "Daniel may be eligible for additional 2x/week supervised PT, but approval still "
                "depends on medical-necessity review and the missing items in the packet."
            )
        else:
            eligibility_answer = (
                "Daniel looks likely eligible for additional 2x/week supervised PT under the fixed "
                "demo assumptions and the current evidence package."
            )

        documentation_items = self._format_requirement_list(orchestrator_output.blocking_requirements)
        documentation_items = self._dedupe_strings(documentation_items)
        documentation_answer = (
            "Approval would be strengthened by objective functional deficit measurements, a structured "
            "supervised PT plan, physician justification, and documentation that the prior rehab course "
            "was incomplete."
        )
        if documentation_items:
            documentation_answer = "Approval would be strengthened by: " + "; ".join(documentation_items) + "."

        if clinical_output.decision.recommended_path == CarePath.ADDITIONAL_STRUCTURED_PT:
            next_care_answer = (
                "The next care plan should be a time-bounded supervised PT block focused on objective "
                "strength and movement deficits, followed by reassessment. Escalate to surgical review "
                "if instability worsens or structured PT fails."
            )
        elif clinical_output.decision.recommended_path == CarePath.SURGICAL_REEVALUATION:
            next_care_answer = (
                "The next care plan should shift to surgical re-evaluation rather than continued PT-only management."
            )
        else:
            next_care_answer = (
                "The next care plan should first close the missing clinical information gap before deciding on "
                "additional PT versus surgical re-evaluation."
            )

        supporting_refs = self._supporting_evidence_refs(orchestrator_input)
        sections = [
            ExternalAnswerSection(
                topic="eligibility",
                answer=eligibility_answer,
                confidence=self._topic_confidence(
                    insurance_output.confidence.value,
                    benefits_output.confidence.value,
                ),
                supporting_points=eligibility_points,
                supporting_evidence_refs=supporting_refs,
            ),
            ExternalAnswerSection(
                topic="documentation",
                answer=documentation_answer,
                confidence=self._topic_confidence(insurance_output.confidence.value),
                supporting_points=documentation_items,
                supporting_evidence_refs=supporting_refs,
            ),
            ExternalAnswerSection(
                topic="next_care_plan",
                answer=next_care_answer,
                confidence=self._topic_confidence(clinical_output.confidence.value),
                supporting_points=[step.action for step in orchestrator_output.recommended_workflow[:3]],
                supporting_evidence_refs=[item.source_ref for item in clinical_output.evidence[:3]],
            ),
        ]

        short_answer = (
            "Daniel may be eligible for additional 2x/week supervised PT, but approval depends on a "
            "stronger packet with objective deficits, a structured PT plan, physician justification, "
            "and documentation of the incomplete prior rehab course."
        )
        if clinical_output.decision.recommended_path == CarePath.SURGICAL_REEVALUATION:
            short_answer = (
                "The current clinical picture points more toward surgical re-evaluation than additional PT."
            )
        elif not documentation_items and not blocking_items:
            short_answer = (
                "Daniel looks likely eligible for additional 2x/week supervised PT under the demo assumptions."
            )

        recommended_next_steps = self._dedupe_strings(
            [step.action for step in orchestrator_output.recommended_workflow]
        )
        open_questions = [item.question for item in orchestrator_output.open_questions]

        return ExternalAgentResponse(
            case_id=case.case_id,
            user_question=user_question,
            short_answer=short_answer,
            readiness=orchestrator_output.case_resolution.readiness,
            requires_human_review=orchestrator_output.case_resolution.requires_human_review,
            sections=sections,
            recommended_next_steps=recommended_next_steps,
            blocking_items=blocking_items,
            benefits_at_a_glance=orchestrator_output.benefits_summary,
            open_questions=open_questions,
        )

    def run_debug(self, user_question: str, case: CaseData) -> RunCaseDebugResponse:
        clinical_input = self.build_clinical_input(user_question, case)
        clinical_output = self.clinical_agent.run(clinical_input)

        insurance_input = self.build_insurance_input(
            user_question=user_question,
            clinical_output=clinical_output,
        )
        insurance_output = self.insurance_agent.run(insurance_input)
        insurance_benefits_input = self.build_insurance_benefits_input(
            user_question=user_question,
            clinical_output=clinical_output,
        )
        insurance_benefits_output = self.insurance_benefits_agent.run(insurance_benefits_input)

        orchestrator_input = OrchestratorInput(
            user_question=user_question,
            clinical_output=clinical_output,
            insurance_output=insurance_output,
            insurance_benefits_output=insurance_benefits_output,
        )
        orchestrator_output = self.build_final_output(orchestrator_input)

        return RunCaseDebugResponse(
            clinical_input=clinical_input,
            clinical_output=clinical_output,
            insurance_input=insurance_input,
            insurance_output=insurance_output,
            insurance_benefits_input=insurance_benefits_input,
            insurance_benefits_output=insurance_benefits_output,
            orchestrator_input=orchestrator_input,
            orchestrator_output=orchestrator_output,
        )

    def run(self, user_question: str, case: CaseData) -> ExternalAgentResponse:
        debug_response = self.run_debug(user_question=user_question, case=case)
        return self._build_external_response(
            case=case,
            user_question=user_question,
            orchestrator_input=debug_response.orchestrator_input,
            orchestrator_output=debug_response.orchestrator_output,
        )
