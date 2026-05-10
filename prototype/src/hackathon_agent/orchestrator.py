import logging
import time

from .clinical_llm_agent import ClinicalLLMAgent
from .claude_llm import ClaudeStructuredLLM
from .insurance_llm_agent import InsuranceLLMAgent
from .insurance_retriever import InsurancePolicyRetriever
from .prompt_opinion_agent import PromptOpinionAgent
from .llm import StructuredLLM

logger = logging.getLogger(__name__)
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

_DEMO_BENEFITS = [
    "Fixed demo plan: Kaiser Foundation Health Plan of Washington VisitsPlus Silver 4500 (2026).",
    "Outpatient physical therapy and rehabilitation: covered subject to plan rules.",
    "Preauthorization not required for outpatient PT under the fixed demo plan.",
    "Rehabilitation benefit: up to 25 outpatient visits per calendar year.",
    "Outpatient specialty rehab office visit copay: $75 per visit.",
    "Annual deductible: $4,500 per member / $9,000 per family.",
    "Out-of-pocket maximum: $9,800 per member / $19,600 per family per calendar year.",
    "Covered services must be received from a Network Provider at a Network Facility.",
]


class Orchestrator:
    def __init__(
        self,
        *,
        clinical_agent: ClinicalLLMAgent,
        insurance_agent: InsuranceLLMAgent,
        prompt_opinion_agent: PromptOpinionAgent | None = None,
        llm: StructuredLLM | None = None,
    ) -> None:
        self.clinical_agent = clinical_agent
        self.insurance_agent = insurance_agent
        self.prompt_opinion_agent = prompt_opinion_agent
        self.llm = llm

    @classmethod
    def from_env(cls) -> "Orchestrator":
        llm = ClaudeStructuredLLM()
        return cls(
            clinical_agent=ClinicalLLMAgent(llm),
            insurance_agent=InsuranceLLMAgent(
                llm=llm,
                retriever=InsurancePolicyRetriever(),
            ),
            prompt_opinion_agent=PromptOpinionAgent(llm),
            llm=llm,
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

    def resolve_conflicts(self, orchestrator_input: OrchestratorInput) -> list[ConflictItem]:
        conflicts: list[ConflictItem] = []
        clinical_output = orchestrator_input.clinical_output
        insurance_output = orchestrator_input.insurance_output

        if (
            clinical_output.decision.recommended_path == CarePath.ADDITIONAL_STRUCTURED_PT
            and insurance_output.decision.coverage_position.value == "likely_denied"
        ):
            conflicts.append(
                ConflictItem(
                    conflict_type="clinical_insurance_mismatch",
                    between=["clinical", "insurance"],
                    reason=(
                        "Clinical path recommends additional PT while insurance position "
                        "trends toward denial."
                    ),
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

    def _get_pending_documentation_readiness(self) -> Readiness:
        """
        Prefer Readiness.PENDING_DOCUMENTATION if it exists.

        If your schemas.py does not yet define it, add this:

            PENDING_DOCUMENTATION = "pending_documentation"

        This fallback prevents the app from crashing before the schema is updated,
        but the recommended final state is to add the enum value.
        """
        return getattr(Readiness, "PENDING_DOCUMENTATION", Readiness.NEED_MORE_INFO)

    def _derive_readiness(
        self,
        *,
        clinical_output,
        insurance_output,
        blocking_requirements: list[RequirementItem],
        conflict_items: list[ConflictItem],
    ) -> Readiness:
        if clinical_output.decision.recommended_path == CarePath.NEED_MORE_INFORMATION:
            return Readiness.NEED_MORE_INFO

        if conflict_items:
            return Readiness.BLOCKED

        coverage_position = insurance_output.decision.coverage_position.value

        if coverage_position == "likely_denied":
            return Readiness.BLOCKED

        if blocking_requirements:
            return self._get_pending_documentation_readiness()

        return Readiness.READY

    def _requires_human_review(
        self,
        *,
        readiness: Readiness,
        conflict_items: list[ConflictItem],
        blocking_requirements: list[RequirementItem],
    ) -> bool:
        if conflict_items:
            return True

        if blocking_requirements:
            return True

        if readiness in {
            Readiness.BLOCKED,
            Readiness.NEED_MORE_INFO,
            self._get_pending_documentation_readiness(),
        }:
            return True

        return False

    def build_final_output(self, orchestrator_input: OrchestratorInput) -> OrchestratorOutput:
        clinical_output = orchestrator_input.clinical_output
        insurance_output = orchestrator_input.insurance_output
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
                    question=(
                        "What objective strength and functional measurements can be attached "
                        "to support the PT request?"
                    ),
                )
            )

        insurance_requirement_codes = {item.code for item in insurance_output.requirements}
        if "document_incomplete_rehab_course" in insurance_requirement_codes:
            open_questions.append(
                QuestionItem(
                    code="prior_rehab_gap_documentation",
                    question=(
                        "What documentation proves that the prior post-revision rehabilitation "
                        "course was incomplete?"
                    ),
                )
            )

        readiness = self._derive_readiness(
            clinical_output=clinical_output,
            insurance_output=insurance_output,
            blocking_requirements=blocking_requirements,
            conflict_items=conflict_items,
        )

        requires_human_review = self._requires_human_review(
            readiness=readiness,
            conflict_items=conflict_items,
            blocking_requirements=blocking_requirements,
        )

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
                action=(
                    "Define a structured supervised PT plan with frequency and reassessment window."
                ),
                depends_on=["clinical_collect_deficits"],
                done_definition="A time-bounded PT plan is available for submission.",
            ),
            WorkflowStep(
                step_id="insurance_prepare_packet",
                owner=WorkflowOwner.INSURANCE,
                action=(
                    "Prepare coverage support packet with objective deficits, prior rehab "
                    "documentation, and therapy plan."
                ),
                depends_on=["clinical_collect_deficits", "clinical_define_pt_plan"],
                done_definition=(
                    "Support packet includes objective deficits, prior rehab documentation, "
                    "and a structured therapy plan."
                ),
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
                requires_human_review=requires_human_review,
            ),
            key_evidence=clinical_output.evidence,
            blocking_requirements=blocking_requirements,
            benefits_summary=list(_DEMO_BENEFITS),
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
                    "Treat this as decision support, not an automated coverage approval.",
                ],
            ),
            open_questions=open_questions,
            escalation_reason="Blocking conflict exists." if conflict_items else "",
        )

    def _confidence_rank(self, confidence: str) -> int:
        return {"low": 0, "medium": 1, "high": 2}.get(confidence, 0)

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

        return self._dedupe_strings(refs)

    def _format_requirement_list(self, requirements: list[RequirementItem]) -> list[str]:
        return [
            self._clean_sentence(item.description)
            for item in requirements
            if item.status != RequirementStatus.SATISFIED
        ]

    def _dedupe_strings(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()

        for value in values:
            cleaned = value.strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            deduped.append(cleaned)

        return deduped

    def _clean_sentence(self, value: str) -> str:
        value = value.strip()
        if not value:
            return value
        return value.rstrip(".; ") + "."

    def _case_display_name(self, case: CaseData) -> str:
        summary = case.patient_summary or ""
        if "Daniel" in summary:
            return "Daniel"
        return "The patient"

    def _format_documentation_gap_answer(self, documentation_items: list[str]) -> str:
        if not documentation_items:
            return "No major documentation gaps were identified."

        return (
            "Approval would be strengthened by three documentation updates: a detailed prior "
            "rehabilitation history, objective strength and functional movement measurements, "
            "and a structured supervised PT plan with goals, frequency, duration, progression "
            "criteria, and reassessment timing."
        )

    def _build_decision_logic(
        self,
        *,
        clinical_output,
        insurance_output,
        blocking_items: list[str],
    ) -> list[str]:
        """Build 3-step decision logic summary."""
        clinical_confidence = clinical_output.confidence.value.upper()
        insurance_confidence = insurance_output.confidence.value.upper()
        orchestrator_confidence = self._min_confidence(
            clinical_output.confidence.value,
            insurance_output.confidence.value,
        ).upper()

        # Step 1: Clinical
        path = clinical_output.decision.recommended_path.value
        if path == "additional_structured_pt":
            clinical_step = (
                f"Step 1 [Clinical — {clinical_confidence}]: PT is medically necessary. "
                "Imaging shows intact graft; instability is rehabilitation-related, not structural."
            )
        elif path == "surgical_reevaluation":
            clinical_step = (
                f"Step 1 [Clinical — {clinical_confidence}]: Surgical re-evaluation recommended. "
                "Clinical findings suggest structural issue or failed nonsurgical management."
            )
        else:
            clinical_step = (
                f"Step 1 [Clinical — {clinical_confidence}]: More clinical information needed "
                "before recommending PT or surgery."
            )

        # Step 2: Insurance
        coverage_pos = insurance_output.decision.coverage_position.value
        if coverage_pos == "likely_covered":
            insurance_step = (
                f"Step 2 [Insurance — {insurance_confidence}]: PT is covered under the plan. "
                "No pre-authorization required."
            )
        elif coverage_pos == "conditionally_covered_pending_documentation":
            insurance_step = (
                f"Step 2 [Insurance — {insurance_confidence}]: PT is covered (25 visits/year, "
                "no pre-auth required). Conditional on submitting documentation."
            )
        elif coverage_pos == "likely_denied":
            insurance_step = (
                f"Step 2 [Insurance — {insurance_confidence}]: Coverage likely denied. "
                "Review blocking requirements before submission."
            )
        else:
            insurance_step = (
                f"Step 2 [Insurance — {insurance_confidence}]: Insurance coverage unclear. "
                "Manual review required."
            )

        # Step 3: Orchestrator
        block_count = len(blocking_items)
        if block_count == 0:
            orchestrator_step = (
                f"Step 3 [Orchestrator — {orchestrator_confidence}]: No blocking items identified. "
                "Case is ready for submission."
            )
        else:
            plural = "s" if block_count != 1 else ""
            orchestrator_step = (
                f"Step 3 [Orchestrator — {orchestrator_confidence}]: Structured PT recommended. "
                f"{block_count} item{plural} blocking insurance approval — "
                "submit documentation to proceed."
            )

        return [clinical_step, insurance_step, orchestrator_step]

    def _build_blocking_items_with_context(
        self,
        blocking_requirements: list[RequirementItem],
        conflict_items: list[ConflictItem],
    ) -> list[str]:
        """Format blocking items with owner context."""
        items = []

        for req in blocking_requirements:
            if req.status == RequirementStatus.SATISFIED:
                continue
            owner_label = req.owner.value.title() if req.owner else "Unknown"
            desc = self._clean_sentence(req.description)
            items.append(f"[{owner_label}] {desc}")

        for conflict in conflict_items:
            items.append(f"[Conflict] {self._clean_sentence(conflict.reason)}")

        return self._dedupe_strings(items)

    def _build_insurance_supporting_points(self, coverage_rules: list) -> list[str]:
        """Build policy-specific supporting points from coverage rules."""
        points = []
        for rule in coverage_rules:
            status = "UNSATISFIED" if rule.unsatisfied_reason else "SATISFIED"
            text = f"[{status}] {rule.rule_id}: {rule.rule_text}"
            if rule.unsatisfied_reason:
                text += f" (missing: {rule.unsatisfied_reason})"
            points.append(text)
        return points

    def _build_short_answer(
        self,
        *,
        case: CaseData,
        insurance_output,
        blocking_items: list[str],
        readiness: Readiness,
    ) -> str:
        name = self._case_display_name(case)
        coverage_position = insurance_output.decision.coverage_position.value
        pending_documentation = self._get_pending_documentation_readiness()

        if coverage_position == "likely_denied":
            return (
                f"{name}'s request for additional supervised PT is unlikely to be approved with "
                "the current packet. The strongest next step is to resolve the missing clinical "
                "documentation and review denial or appeal risks before submission."
            )

        if readiness == pending_documentation or blocking_items:
            return (
                f"{name} is likely a reasonable candidate for additional supervised PT, but the "
                "case is pending documentation before it is insurance-ready. Approval would be "
                "strengthened by objective strength and functional testing, prior rehab history, "
                "and a structured PT plan with frequency, duration, goals, progression criteria, "
                "and reassessment timing."
            )

        if readiness == Readiness.NEED_MORE_INFO:
            return (
                f"{name}'s case needs more clinical information before deciding whether additional "
                "PT or surgical re-evaluation is the best next step."
            )

        if readiness == Readiness.BLOCKED:
            return (
                f"{name}'s case has a blocking clinical or insurance issue that should be reviewed "
                "before submission."
            )

        return (
            f"{name}'s case appears ready for review based on the available clinical and insurance "
            "information. The recommended next step is to submit a structured support packet."
        )

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

        blocking_items = self._build_blocking_items_with_context(
            orchestrator_output.blocking_requirements,
            orchestrator_output.conflict_items,
        )

        # Use actual policy rule text for eligibility section
        eligibility_points = self._build_insurance_supporting_points(
            insurance_output.coverage_rules
        )
        if not eligibility_points:
            eligibility_points = [
                f"Authorization signal: {insurance_output.decision.coverage_position.value}.",
            ]

        if insurance_output.decision.coverage_position.value == "likely_denied":
            eligibility_answer = (
                "With the current packet, approval for additional 2x/week supervised PT looks unlikely."
            )
        elif blocking_items:
            eligibility_answer = (
                "Daniel may be eligible for additional 2x/week supervised PT, but approval still "
                "depends on medical-necessity review and the missing documentation items in the packet."
            )
        else:
            eligibility_answer = (
                "Daniel looks likely eligible for additional 2x/week supervised PT under the fixed "
                "demo assumptions and the current evidence package."
            )

        documentation_items = self._format_requirement_list(
            orchestrator_output.blocking_requirements
        )
        documentation_items = self._dedupe_strings(documentation_items)
        documentation_answer = self._format_documentation_gap_answer(documentation_items)

        if clinical_output.decision.recommended_path == CarePath.ADDITIONAL_STRUCTURED_PT:
            next_care_answer = (
                "The next care plan should be a time-bounded supervised PT block focused on objective "
                "strength and movement deficits, followed by reassessment. Escalate to surgical review "
                "if instability worsens or structured PT fails."
            )
        elif clinical_output.decision.recommended_path == CarePath.SURGICAL_REEVALUATION:
            next_care_answer = (
                "The next care plan should shift to surgical re-evaluation rather than continued "
                "PT-only management."
            )
        else:
            next_care_answer = (
                "The next care plan should first close the missing clinical information gap before "
                "deciding on additional PT versus surgical re-evaluation."
            )

        supporting_refs = self._supporting_evidence_refs(orchestrator_input)

        # Build supporting points with bounds checking
        injury_history_points = [pt for pt in case.clinical_notes[:2]] + case.pt_notes[:3]
        injury_history_refs = [f"clinical_notes[{i}]" for i in range(min(2, len(case.clinical_notes)))] + \
                              [f"pt_notes[{i}]" for i in range(min(3, len(case.pt_notes)))]

        clinical_status_points = [pt for pt in case.clinical_notes[2:5]] + case.pt_notes[3:4] + case.imaging
        clinical_status_refs = [f"clinical_notes[{i}]" for i in range(2, min(5, len(case.clinical_notes)))] + \
                               (["pt_notes[3]"] if len(case.pt_notes) > 3 else []) + \
                               [f"imaging[{i}]" for i in range(len(case.imaging))]

        sections = [
            ExternalAnswerSection(
                topic="case_context",
                answer=case.patient_summary,
                confidence=self._topic_confidence(clinical_output.confidence.value),
                supporting_points=[case.patient_summary],
                supporting_evidence_refs=["patient_summary"],
            ),
            ExternalAnswerSection(
                topic="injury_and_rehab_history",
                answer=(
                    "Daniel had primary ACL reconstruction about 2.5 years ago and revision ACL "
                    "reconstruction 8 months ago. His first rehab course lasted about 10 weeks but "
                    "did not complete return-to-sport progression. His revision-surgery rehab lasted "
                    "only 4 to 5 weeks and did not document structured strengthening or neuromuscular "
                    "progression."
                ),
                confidence=self._topic_confidence(clinical_output.confidence.value),
                supporting_points=injury_history_points,
                supporting_evidence_refs=injury_history_refs,
            ),
            ExternalAnswerSection(
                topic="current_clinical_status",
                answer=(
                    "Current symptoms include activity-related knee pain, mild laxity, quadriceps "
                    "weakness, poor neuromuscular control, and fear of re-injury. Imaging shows an "
                    "intact ACL graft with mild stretching, mild effusion and early cartilage "
                    "degeneration, and no acute tear or displaced hardware complication."
                ),
                confidence=self._topic_confidence(clinical_output.confidence.value),
                supporting_points=clinical_status_points,
                supporting_evidence_refs=clinical_status_refs,
            ),
            ExternalAnswerSection(
                topic="insurance_authorization",
                answer=eligibility_answer,
                confidence=self._topic_confidence(insurance_output.confidence.value),
                supporting_points=eligibility_points if eligibility_points else documentation_items,
                supporting_evidence_refs=supporting_refs,
            ),
            ExternalAnswerSection(
                topic="documentation_gaps",
                answer=documentation_answer,
                confidence=self._topic_confidence(insurance_output.confidence.value),
                supporting_points=(
                    self._build_insurance_supporting_points(insurance_output.coverage_rules)
                    or documentation_items
                ),
                supporting_evidence_refs=supporting_refs,
            ),
            ExternalAnswerSection(
                topic="next_care_plan",
                answer=next_care_answer,
                confidence=self._topic_confidence(clinical_output.confidence.value),
                supporting_points=[
                    step.action for step in orchestrator_output.recommended_workflow[:3]
                ],
                supporting_evidence_refs=[
                    item.source_ref for item in clinical_output.evidence[:3]
                ],
            ),
        ]

        short_answer = self._build_short_answer(
            case=case,
            insurance_output=insurance_output,
            blocking_items=blocking_items,
            readiness=orchestrator_output.case_resolution.readiness,
        )

        recommended_next_steps = self._dedupe_strings(
            [step.action for step in orchestrator_output.recommended_workflow]
        )

        decision_logic = self._build_decision_logic(
            clinical_output=clinical_output,
            insurance_output=insurance_output,
            blocking_items=blocking_items,
        )

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
            open_questions=[item.question for item in orchestrator_output.open_questions],
            decision_logic=decision_logic,
        )

    def run_debug(self, user_question: str, case: CaseData) -> RunCaseDebugResponse:
        t_start = time.time()

        clinical_input = self.build_clinical_input(user_question, case)
        t0 = time.time()
        clinical_output = self.clinical_agent.run(clinical_input)
        clinical_time = time.time() - t0
        logger.info(f"⏱️  Clinical agent: {clinical_time:.2f}s")

        insurance_input = self.build_insurance_input(
            user_question=user_question,
            clinical_output=clinical_output,
        )
        t1 = time.time()
        insurance_output = self.insurance_agent.run(insurance_input)
        insurance_time = time.time() - t1
        logger.info(f"⏱️  Insurance agent: {insurance_time:.2f}s")

        orchestrator_input = OrchestratorInput(
            user_question=user_question,
            clinical_output=clinical_output,
            insurance_output=insurance_output,
        )
        t2 = time.time()
        orchestrator_output = self.build_final_output(orchestrator_input)
        orchestrator_time = time.time() - t2
        logger.info(f"⏱️  Orchestrator: {orchestrator_time:.2f}s")

        total_time = time.time() - t_start
        logger.info(f"⏱️  TOTAL: {total_time:.2f}s (clinical={clinical_time:.2f}s, insurance={insurance_time:.2f}s, orchestrator={orchestrator_time:.2f}s)")

        return RunCaseDebugResponse(
            clinical_input=clinical_input,
            clinical_output=clinical_output,
            insurance_input=insurance_input,
            insurance_output=insurance_output,
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

    def generate_opinion(self, response: ExternalAgentResponse) -> str:
        """Generate plain-language clinical summary from structured response.

        Translates the structured ExternalAgentResponse into a markdown summary
        suitable for care coordinators, patients, and the Prompt Opinion platform.

        Args:
            response: ExternalAgentResponse from orchestrator containing structured case analysis

        Returns:
            Plain-language markdown summary

        Raises:
            RuntimeError: If prompt_opinion_agent is not configured
        """
        if self.prompt_opinion_agent is None:
            raise RuntimeError(
                "PromptOpinionAgent is not configured. "
                "Wire a PromptOpinionAgent before calling generate_opinion()."
            )
        return self.prompt_opinion_agent.run(response)
