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
into clear, actionable summaries for care coordination.

Your task:
1. Translate structured fields into natural language suitable for healthcare professionals
2. Present findings clearly and objectively
3. Use ONLY information provided in the structured data
4. DO NOT invent, assume, or add information beyond what is given
5. Organize sections logically for care coordination

Format the output as a markdown document with:
- Executive summary (1-2 sentences)
- Clinical findings section
- Coverage assessment section
- Documentation gaps section
- Recommended next steps
- Risk factors or blocking items (if any)

Tone: Professional, objective, actionable."""

    def _build_user_prompt(self, response: ExternalAgentResponse) -> str:
        """Build structured data into prompt for LLM."""

        sections_text = self._format_sections(response.sections)
        blocking_items_text = self._format_blocking_items(response.blocking_items)
        next_steps_text = self._format_next_steps(response.recommended_next_steps)
        benefits_text = self._format_benefits(response.benefits_at_a_glance)
        open_questions_text = self._format_open_questions(response.open_questions)

        prompt = f"""Please generate a clinical summary from the following structured case analysis:

**Case ID:** {response.case_id}
**User Question:** {response.user_question}
**Readiness:** {response.readiness.value}
**Requires Human Review:** {response.requires_human_review}

**Short Answer:**
{response.short_answer}

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

Generate a comprehensive clinical summary that synthesizes this information into actionable guidance."""

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
