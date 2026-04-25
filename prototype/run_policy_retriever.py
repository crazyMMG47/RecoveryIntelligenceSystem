from __future__ import annotations

from hackathon_agent.clinical_llm_agent import ClinicalLLMAgent
from hackathon_agent.demo_data import DEMO_CASE
from hackathon_agent.gemini_llm import GeminiStructuredLLM
from hackathon_agent.insurance_retriever import InsurancePolicyRetriever
from hackathon_agent.schemas import ClinicalAgentInput, InsuranceAgentInput


def main() -> None:
    llm = GeminiStructuredLLM()
    clinical_agent = ClinicalLLMAgent(llm)

    user_question = (
        "Is Daniel likely eligible for additional 2x/week PT under his Kaiser plan, "
        "and what documentation would strengthen approval?"
    )

    clinical_input = ClinicalAgentInput(
        question=user_question,
        patient_summary=DEMO_CASE.patient_summary,
        clinical_notes=DEMO_CASE.clinical_notes,
        pt_notes=DEMO_CASE.pt_notes,
        imaging=DEMO_CASE.imaging,
    )
    clinical_output = clinical_agent.run(clinical_input)
    insurance_input = InsuranceAgentInput(
        question=user_question,
        clinical_decision=clinical_output.decision,
        clinical_evidence=clinical_output.evidence,
        clinical_requirements=clinical_output.requirements,
    )

    retriever = InsurancePolicyRetriever()
    for bucket in retriever.retrieve(insurance_input):
        print(f"\n=== {bucket.bucket_name} ===")
        print(f"query: {bucket.query}")
        print(f"confidence: {bucket.confidence:.2f}")
        for note in bucket.notes:
            print(f"note: {note}")
        for chunk in bucket.chunks:
            print(f"\n[{chunk.source_ref}] {chunk.title}")
            print(f"section: {chunk.section}")
            print(f"bucket: {chunk.bucket}")
            print(f"url: {chunk.url}")
            print(chunk.text[:800])


if __name__ == "__main__":
    main()
