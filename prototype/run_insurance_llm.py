from __future__ import annotations

import json

from hackathon_agent.clinical_llm_agent import ClinicalLLMAgent
from hackathon_agent.demo_data import DEMO_CASE
from hackathon_agent.gemini_llm import GeminiStructuredLLM
from hackathon_agent.insurance_llm_agent import InsuranceLLMAgent
from hackathon_agent.insurance_retriever import InsurancePolicyRetriever
from hackathon_agent.schemas import ClinicalAgentInput, InsuranceAgentInput


def main() -> None:
    llm = GeminiStructuredLLM()

    clinical_agent = ClinicalLLMAgent(llm)
    clinical_payload = ClinicalAgentInput(
        question=(
            "Given the patient's clinical status after revision ACL reconstruction, "
            "what is the most appropriate next clinical path?"
        ),
        patient_summary=DEMO_CASE.patient_summary,
        clinical_notes=DEMO_CASE.clinical_notes,
        pt_notes=DEMO_CASE.pt_notes,
        imaging=DEMO_CASE.imaging,
    )
    clinical_result = clinical_agent.run(clinical_payload)

    insurance_agent = InsuranceLLMAgent(
        llm=llm,
        retriever=InsurancePolicyRetriever(),
        debug=True,
    )
    insurance_payload = InsuranceAgentInput(
        question=(
            "Is Daniel likely eligible for additional 2x/week PT under his Kaiser plan, "
            "and what documentation would strengthen approval?"
        ),
        clinical_decision=clinical_result.decision,
        clinical_evidence=clinical_result.evidence,
        clinical_requirements=clinical_result.requirements,
    )

    insurance_result = insurance_agent.run(insurance_payload)
    print(json.dumps(insurance_result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
