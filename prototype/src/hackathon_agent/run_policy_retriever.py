from __future__ import annotations

import sys
from pathlib import Path

# project root = .../RecoveryIntelligenceSystem/prototype
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    
from kp.bucketed_policy_retriever import BucketedPolicyRetriever   

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
    retriever = BucketedPolicyRetriever(top_k_per_bucket=3)

    payload = InsuranceAgentInput(
        question=(
            "Is additional 2x/week physical therapy medically necessary, "
            "and what documentation is needed for approval?"
        ),
        policy_text=None,
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

    buckets = retriever.retrieve(payload)

    print(f"\nRetrieved {len(buckets)} bucket(s)\n")

    for bucket in buckets:
        print("=" * 90)
        print(f"BUCKET: {bucket.bucket_name}")
        print(f"QUERY: {bucket.query}")
        print(f"CONFIDENCE: {bucket.confidence:.2f}")

        if bucket.notes:
            print("NOTES:")
            for note in bucket.notes:
                print(f"  - {note}")

        if not bucket.chunks:
            print("[WARN] No chunks retrieved for this bucket.\n")
            continue

        print(f"\nRetrieved {len(bucket.chunks)} chunk(s) for this bucket:\n")

        for i, chunk in enumerate(bucket.chunks, start=1):
            print(f"--- Chunk {i} ---")
            print("source_ref:", chunk.source_ref)
            print("title:", chunk.title)
            print("section:", chunk.section)
            print("bucket:", chunk.bucket)
            print("url:", chunk.url)
            print(chunk.text[:1200])
            print("\n")

    print("=" * 90)
    print("Done.\n")


if __name__ == "__main__":
    main()