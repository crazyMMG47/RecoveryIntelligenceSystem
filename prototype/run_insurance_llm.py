from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import json

from src.hackathon_agent.ollama_llm import OllamaStructuredLLM
from src.hackathon_agent.insurance_llm_agent import InsuranceLLMAgent
from src.hackathon_agent.insurance_retriever import InsurancePolicyRetriever
from src.hackathon_agent.schemas import (
    CarePath,
    ClinicalDecision,
    EvidenceItem,
    EvidenceStrength,
    InsuranceAgentInput,
    RecommendationDisposition,
    RequirementItem,
    RequirementStatus,
    SourceType,
    WorkflowOwner,
)

MOCK_CLINICAL_DECISION = ClinicalDecision(
    recommended_service="Outpatient physical therapy",
    recommendation_disposition=RecommendationDisposition.RECOMMEND,
    recommended_path=CarePath.ADDITIONAL_STRUCTURED_PT,
    recommendation_reason_codes=[
        "persistent_instability_post_revision",
        "quadriceps_weakness",
        "incomplete_prior_rehabilitation",
        "poor_neuromuscular_control",
    ],
)

MOCK_CLINICAL_EVIDENCE = [
    EvidenceItem(
        code="acl_revision_x2",
        statement=(
            "Patient has undergone two ACL reconstructions at different Kaiser "
            "locations with inconsistent rehabilitation protocols."
        ),
        source_type=SourceType.CLINICAL_NOTE,
        source_ref="clinical_note_1",
        supports="need_for_structured_pt",
        strength=EvidenceStrength.STRONG,
    ),
    EvidenceItem(
        code="post_revision_rehab_incomplete",
        statement=(
            "First surgery: PT completed ~10 weeks but did not finish "
            "return-to-sport phase. Second surgery: PT lasted only 4-5 weeks, "
            "focused on pain control only, no structured strength training."
        ),
        source_type=SourceType.PT_NOTE,
        source_ref="pt_note_1",
        supports="incomplete_prior_rehab_course",
        strength=EvidenceStrength.STRONG,
    ),
    EvidenceItem(
        code="quadriceps_weakness",
        statement=(
            "Significant quadriceps weakness, poor neuromuscular control, "
            "fear of re-injury, mild laxity on exam."
        ),
        source_type=SourceType.CLINICAL_NOTE,
        source_ref="clinical_note_2",
        supports="objective_functional_deficit",
        strength=EvidenceStrength.MODERATE,
    ),
    EvidenceItem(
        code="imaging_graft_stretch",
        statement=(
            "MRI shows intact ACL graft with signs of stretching, mild joint "
            "effusion, early cartilage degeneration. Suboptimal graft integrity "
            "with functional instability."
        ),
        source_type=SourceType.IMAGING,
        source_ref="imaging_1",
        supports="functional_instability",
        strength=EvidenceStrength.MODERATE,
    ),
]

MOCK_CLINICAL_REQUIREMENTS = [
    RequirementItem(
        code="objective_deficit_measurement",
        description="Objective strength and functional movement measurements must be attached.",
        owner=WorkflowOwner.CLINICAL,
        status=RequirementStatus.UNSATISFIED,
    ),
    RequirementItem(
        code="structured_pt_plan_definition",
        description="A structured supervised PT plan with frequency and reassessment window must be defined.",
        owner=WorkflowOwner.CLINICAL,
        status=RequirementStatus.UNSATISFIED,
    ),
]


def main() -> None:
    print("=" * 60)
    print("Insurance Agent — Isolated Test")
    print("Patient: Daniel Lee | ACL revision | Kaiser WA")
    print("=" * 60)

    retriever = InsurancePolicyRetriever()

    print("\n--- RAG Retrieval Preview ---")
    preview_payload = InsuranceAgentInput(
        question=(
            "Is Daniel eligible for 2x/week PT under his Kaiser plan, "
            "and what documentation would strengthen approval?"
        ),
        clinical_decision=MOCK_CLINICAL_DECISION,
        clinical_evidence=MOCK_CLINICAL_EVIDENCE,
        clinical_requirements=MOCK_CLINICAL_REQUIREMENTS,
    )
    for bucket in retriever.retrieve(preview_payload):
        print(f"\n  [{bucket.bucket_name}] confidence={bucket.confidence:.2f} | {len(bucket.chunks)} chunk(s)")
        for chunk in bucket.chunks:
            score = bucket.scores.get(chunk.source_ref, 0.0)
            print(f"    [{score:.4f}] {chunk.section or chunk.title} | {chunk.text[:80]}...")

    print("\n--- Running Insurance Agent ---\n")
    llm = OllamaStructuredLLM(model="qwen2.5:7b")
    insurance_agent = InsuranceLLMAgent(llm=llm, retriever=retriever, debug=True)

    insurance_payload = InsuranceAgentInput(
        question=(
            "Is Daniel likely eligible for additional 2x/week PT under his "
            "Kaiser plan, and what documentation would strengthen approval?"
        ),
        clinical_decision=MOCK_CLINICAL_DECISION,
        clinical_evidence=MOCK_CLINICAL_EVIDENCE,
        clinical_requirements=MOCK_CLINICAL_REQUIREMENTS,
    )

    result = insurance_agent.run(insurance_payload)
    print("\n=== Insurance Agent Output ===")
    print(json.dumps(result.model_dump(mode="json"), indent=2))

    if result.validation_errors:
        print("\n[!] Returned with validation errors (degraded response):")
        for err in result.validation_errors:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
