"""Test the orchestrator with custom questions."""
from __future__ import annotations

import json
import sys
from src.hackathon_agent.orchestrator import Orchestrator
from src.hackathon_agent.demo_data import DEMO_CASE


def test_question(question: str) -> None:
    """Run orchestrator with a custom question and display results."""
    print(f"\n{'='*90}")
    print(f"QUESTION: {question}")
    print(f"{'='*90}\n")

    orchestrator = Orchestrator.from_env()

    try:
        # Run full debug pipeline
        debug_response = orchestrator.run_debug(user_question=question, case=DEMO_CASE)

        # Extract what we care about
        clinical = debug_response.clinical_output
        insurance = debug_response.insurance_output
        orch = debug_response.orchestrator_output

        # ── Clinical Output ──
        print("🏥 CLINICAL AGENT")
        print(f"  Decision: {clinical.decision.recommended_path.upper()}")
        print(f"  Confidence: {clinical.confidence.upper()}")
        print(f"  Reason: {', '.join(clinical.decision.recommendation_reason_codes)}")
        print(f"  Evidence Count: {len(clinical.evidence)}")
        print(f"  Requirements:")
        for req in clinical.requirements:
            print(f"    • {req.description} [{req.status.upper()}]")

        # ── Insurance Output ──
        print("\n💰 INSURANCE AGENT")
        print(f"  Coverage Position: {insurance.decision.coverage_position.upper()}")
        print(f"  Confidence: {insurance.confidence.upper()}")
        print(f"  Review Needed: {insurance.decision.review_needed}")
        print(f"  Coverage Rules: {len(insurance.coverage_rules)}")
        print(f"  Requirements:")
        for req in insurance.requirements:
            print(f"    • {req.description} [{req.status.upper()}]")
        if insurance.validation_errors:
            print(f"  ⚠️  Degraded Mode - Fallback output:")
            for err in insurance.validation_errors:
                print(f"    • {err}")

        # ── Orchestrator Output ──
        print("\n🤖 ORCHESTRATOR")
        print(f"  Case Readiness: {orch.case_resolution.readiness.upper()}")
        print(f"  Requires Human Review: {orch.case_resolution.requires_human_review}")
        print(f"  Recommended Path: {orch.case_resolution.recommended_path.upper()}")

        # ── Conflicts ──
        if orch.conflict_items:
            print(f"\n⚡ CONFLICTS DETECTED ({len(orch.conflict_items)}):")
            for conflict in orch.conflict_items:
                blocking_label = "🔴 BLOCKING" if conflict.blocking else "⚠️  INFORMATIONAL"
                print(f"  {blocking_label}: {conflict.conflict_type}")
                print(f"    Between: {' ↔ '.join(conflict.between)}")
                print(f"    Reason: {conflict.reason}")

        # ── Blocking Requirements ──
        if orch.blocking_requirements:
            print(f"\n🚫 BLOCKING REQUIREMENTS ({len(orch.blocking_requirements)}):")
            for req in orch.blocking_requirements:
                print(f"  • {req.description} [{req.status.upper()}]")

        # ── Workflow Steps ──
        if orch.recommended_workflow:
            print(f"\n📋 RECOMMENDED WORKFLOW ({len(orch.recommended_workflow)} steps):")
            for i, step in enumerate(orch.recommended_workflow, 1):
                print(f"  {i}. [{step.owner.upper()}] {step.action}")
                print(f"     ✓ Done when: {step.done_definition}")
                if step.depends_on:
                    print(f"     → Depends on: {', '.join(step.depends_on)}")

        # ── Open Questions ──
        if orch.open_questions:
            print(f"\n❓ OPEN QUESTIONS ({len(orch.open_questions)}):")
            for q in orch.open_questions:
                print(f"  [{q.code}] {q.question}")

        # ── Escalation ──
        if orch.escalation_reason:
            print(f"\n⬆️  ESCALATION: {orch.escalation_reason}")

        print(f"\n{'='*90}\n")

    except Exception as exc:
        print(f"❌ ERROR: {exc}")
        import traceback
        traceback.print_exc()
        print()


def main() -> None:
    """Run tests with predefined questions or accept user input."""
    print("\n" + "="*90)
    print("ORCHESTRATOR TEST SUITE")
    print("="*90)

    # Predefined questions to test
    questions = [
        "Is Daniel eligible for additional supervised PT?",
        "What documentation is needed to approve PT coverage?",
        "Is Daniel a candidate for surgical re-evaluation?",
        "What's the next care plan for Daniel?",
        "How confident are we in the clinical recommendation?",
    ]

    # If user provides a question via command line, use that instead
    if len(sys.argv) > 1:
        questions = [" ".join(sys.argv[1:])]

    for question in questions:
        test_question(question)


if __name__ == "__main__":
    main()
