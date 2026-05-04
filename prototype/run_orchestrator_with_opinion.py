from __future__ import annotations

import json
from dotenv import load_dotenv
load_dotenv()
from src.hackathon_agent.demo_data import DEMO_CASE
from src.hackathon_agent.orchestrator import Orchestrator


def main() -> None:
    orchestrator = Orchestrator.from_env()

    user_question = (
        "Is Daniel likely eligible for additional 2x/week PT under his Kaiser "
        "plan, what documentation would strengthen approval, and what should the next care plan be?"
    )

    # Run orchestrator pipeline to get structured response
    print("=" * 80)
    print("ORCHESTRATOR: Running clinical → insurance → orchestrator pipeline")
    print("=" * 80)
    response = orchestrator.run(
        user_question=user_question,
        case=DEMO_CASE,
    )

    print("\n1. STRUCTURED RESPONSE (ExternalAgentResponse)")
    print("-" * 80)
    print(json.dumps(response.model_dump(mode="json"), indent=2))

    # Generate plain-language opinion
    print("\n" + "=" * 80)
    print("PROMPT OPINION: Generating plain-language clinical summary")
    print("=" * 80)
    opinion = orchestrator.generate_opinion(response)

    print("\n2. PLAIN-LANGUAGE OPINION (PromptOpinionAgent output)")
    print("-" * 80)
    print(opinion)

    print("\n" + "=" * 80)
    print("INTEGRATION TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
