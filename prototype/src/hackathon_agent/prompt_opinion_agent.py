from __future__ import annotations

from .llm import PromptMessage, StructuredLLM
from .schemas import ExternalAgentResponse


class PromptOpinionAgent:
    """Translates structured ExternalAgentResponse to plain-language summary.

    Takes the structured output from the Orchestrator and generates a clinical
    summary suitable for care coordinators, patients, and documentation systems.
    Uses only the provided structured fields without inventing new information.
    """

    def __init__(self, llm: StructuredLLM) -> None:
        self.llm = llm

    def run(self, response: ExternalAgentResponse) -> str:
        """Generate plain-language summary from structured response.

        Args:
            response: ExternalAgentResponse from Orchestrator containing case analysis

        Returns:
            Plain-language markdown summary suitable for human review
        """
        # Build the prompt from structured data
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(response)

        messages = [
            PromptMessage(role="system", content=system_prompt),
            PromptMessage(role="user", content=user_prompt),
        ]

        # Call LLM to generate summary
        summary = self.llm.generate_text(messages=messages)
        return summary

    def _build_system_prompt(self) -> str:
        return """You are a clinical documentation specialist translating structured case analysis
into clear, actionable summaries for care coordinators.

Your task:
1. Translate structured fields into natural language suitable for healthcare professionals
2. Present findings clearly, objectively, and with explicit confidence levels
3. Use ONLY information provided in the structured data
4. DO NOT invent, assume, or add information beyond what is given
5. Make dependency chains and decision reasoning explicit
6. Directly answer the original question with specificity

Format the output as a markdown document with:
- Direct answer to the original question (e.g., "Is Daniel eligible for 2x/week PT?" → clear YES/NO/CONDITIONAL)
- Decision logic & confidence levels (explain which agents made which decisions and why)
- Clinical assessment section (include source findings)
- Insurance assessment section (include policy requirements and what's missing)
- Documentation gaps section (be specific: what's needed, why, and what it unblocks)
- Recommended next steps (ordered by dependency, not priority)
- Blocking items or risks (if any)

IMPORTANT GUIDANCE:
- Surface confidence levels WITH reasoning (HIGH because X sources agree; MEDIUM because conditional on Y)
- Show dependency chains: "Item A must be completed before insurance approval because rule Z requires it"
- For conditional coverage, explain the exact condition (e.g., "25 visits/calendar year, not weekly frequency")
- Distinguish between what's clinically clear vs. what requires patient action
- Use specifics: "2x/week for 12 weeks = 24 visits" not vague "PT coverage"

Tone: Professional, objective, actionable, transparent about reasoning."""

    def _build_user_prompt(self, response: ExternalAgentResponse) -> str:
        """Build structured data into prompt for LLM."""

        sections_text = self._format_sections(response.sections)
        blocking_items_text = self._format_blocking_items(response.blocking_items)
        next_steps_text = self._format_next_steps(response.recommended_next_steps)
        benefits_text = self._format_benefits(response.benefits_at_a_glance)
        open_questions_text = self._format_open_questions(response.open_questions)
        decision_logic_text = self._format_next_steps(response.decision_logic) if response.decision_logic else "None provided"

        prompt = f"""Please generate a clinical summary from the following structured case analysis:

**Case ID:** {response.case_id}
**User Question:** {response.user_question}
**Readiness:** {response.readiness.value}
**Requires Human Review:** {response.requires_human_review}

**Short Answer:**
{response.short_answer}

**Decision Logic (how agents reached this conclusion):**
{decision_logic_text}

**Detailed Sections:**
{sections_text}

**Plan Benefits (for reference):**
{benefits_text}

**Blocking Items/Concerns:**
{blocking_items_text if blocking_items_text else "None identified"}

**Recommended Next Steps:**
{next_steps_text}

**Open Questions for Clarification:**
{open_questions_text if open_questions_text else "None"}

Generate a comprehensive clinical summary that synthesizes this information into actionable guidance.
Start with a direct answer to the original question. Include confidence levels and the reasoning behind them.
Make explicit any dependencies or conditions (e.g., "approval depends on X because policy rule Y requires it")."""

        return prompt

    def _format_sections(self, sections: list) -> str:
        """Format ExternalAnswerSection objects into readable text."""
        formatted = []
        for section in sections:
            text = f"""**{section.topic.replace('_', ' ').title()}** (Confidence: {section.confidence.value})
Answer: {section.answer}
Supporting Points:
{chr(10).join(f"  - {point}" for point in section.supporting_points)}
"""
            formatted.append(text)
        return "\n".join(formatted)

    def _format_blocking_items(self, items: list[str]) -> str:
        """Format blocking items into readable list."""
        if not items:
            return "None"
        return "\n".join(f"  - {item}" for item in items)

    def _format_next_steps(self, steps: list[str]) -> str:
        """Format recommended next steps into readable list."""
        if not steps:
            return "Review structured recommendations above"
        return "\n".join(f"  {i+1}. {step}" for i, step in enumerate(steps))

    def _format_benefits(self, benefits: list[str]) -> str:
        """Format benefits summary."""
        if not benefits:
            return "No specific plan benefits documented"
        return "\n".join(f"  - {benefit}" for benefit in benefits)

    def _format_open_questions(self, questions: list[str]) -> str:
        """Format open questions."""
        if not questions:
            return "None"
        return "\n".join(f"  - {question}" for question in questions)
