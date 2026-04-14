from __future__ import annotations

import json

from hackathon_agent.demo_data import DEMO_CASE
from hackathon_agent.orchestrator import Orchestrator


def main() -> None:
    orchestrator = Orchestrator.from_env()
    result = orchestrator.run(
        user_question=(
            "Is Daniel likely eligible for additional 2x/week PT under his Kaiser "
            "plan, what documentation would strengthen approval, and what should the next care plan be?"
        ),
        case=DEMO_CASE,
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
