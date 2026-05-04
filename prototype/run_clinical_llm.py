from __future__ import annotations

import json

from src.hackathon_agent.clinical_llm_agent import ClinicalLLMAgent
from src.hackathon_agent.demo_data import DEMO_CASE
from src.hackathon_agent.gemini_llm import GeminiStructuredLLM
from src.hackathon_agent.schemas import ClinicalAgentInput


def main() -> None:
    llm = GeminiStructuredLLM()
    agent = ClinicalLLMAgent(llm)
    payload = ClinicalAgentInput(
        question=(
            "Given the patient's clinical status after revision ACL reconstruction, "
            "what is the most appropriate next clinical path?"
        ),
        patient_summary=DEMO_CASE.patient_summary,
        clinical_notes=DEMO_CASE.clinical_notes,
        pt_notes=DEMO_CASE.pt_notes,
        imaging=DEMO_CASE.imaging,
    )
    result = agent.run(payload)
    print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
