from __future__ import annotations

from policy_retriever import PolicyRetriever
from schemas import (
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


def main() -> None:
    retriever = PolicyRetriever(
        # cache_dir="policy_cache",
        cache_dir="/home/smooi/RecoveryIntelligenceSystem/data/policy_cache",
        # TODO: make relative path 
        top_k=4,
    )

    payload = InsuranceAgentInput(
        question=(
            "Is additional 2x/week physical therapy medically necessary, "
            "and what documentation is needed for approval?"
        ),
        policy_text="",  # IMPORTANT: force real retrieval from cache
        clinical_decision=ClinicalDecision(
            recommended_service="supervised_pt",
            recommendation_disposition=RecommendationDisposition.RECOMMEND,
            recommended_path=CarePath.ADDITIONAL_STRUCTURED_PT,
            recommendation_reason_codes=[
                "documented_quadriceps_weakness",
                "post_revision_rehab_incomplete",
            ],
        ),
        clinical_evidence=[
            EvidenceItem(
                code="documented_quadriceps_weakness",
                statement="Quadriceps weakness is documented.",
                source_type=SourceType.PT_NOTE,
                source_ref="pt_notes[0]",
                supports="supervised_pt",
                strength=EvidenceStrength.STRONG,
            ),
            EvidenceItem(
                code="post_revision_rehab_incomplete",
                statement="Post-revision rehab was incomplete.",
                source_type=SourceType.PT_NOTE,
                source_ref="pt_notes[1]",
                supports="supervised_pt",
                strength=EvidenceStrength.STRONG,
            ),
        ],
        clinical_requirements=[
            RequirementItem(
                code="objective_deficit_measurement",
                description="Need objective testing.",
                owner=WorkflowOwner.CLINICAL,
                status=RequirementStatus.UNSATISFIED,
            )
        ],
    )

    chunks = retriever.retrieve(payload)

    print(f"\nRetrieved {len(chunks)} chunk(s)\n")
    for i, chunk in enumerate(chunks, start=1):
        print(f"=== Chunk {i} ===")
        print("source_ref:", chunk.source_ref)
        print("title:", chunk.title)
        print("url:", chunk.url)
        print(chunk.text[:1200])
        print("\n")


if __name__ == "__main__":
    main()