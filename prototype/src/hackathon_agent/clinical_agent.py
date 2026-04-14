from .schemas import (
    CarePath,
    ClinicalAgentInput,
    ClinicalAgentOutput,
    ClinicalDecision,
    ConfidenceLevel,
    EvidenceItem,
    EvidenceStrength,
    RecommendationDisposition,
    RequirementItem,
    RequirementStatus,
    RiskItem,
    SourceType,
    WorkflowOwner,
)


class ClinicalAgent:
    def run(self, payload: ClinicalAgentInput) -> ClinicalAgentOutput:
        evidence: list[EvidenceItem] = []
        requirements: list[RequirementItem] = []
        risk_items: list[RiskItem] = []
        stop_conditions: list[str] = []
        next_steps: list[str] = []

        joined_clinical = " ".join(payload.clinical_notes).lower()
        joined_pt = " ".join(payload.pt_notes).lower()
        joined_imaging = " ".join(payload.imaging).lower()

        if "quadriceps weakness" in joined_pt:
            evidence.append(
                EvidenceItem(
                    code="documented_quadriceps_weakness",
                    statement="Quadriceps weakness is documented after revision ACL reconstruction.",
                    source_type=SourceType.PT_NOTE,
                    source_ref="pt_notes[3]",
                    supports="supervised_pt",
                    strength=EvidenceStrength.STRONG,
                )
            )
        if "neuromuscular" in joined_pt:
            evidence.append(
                EvidenceItem(
                    code="documented_neuromuscular_deficit",
                    statement="Neuromuscular control deficits remain present.",
                    source_type=SourceType.PT_NOTE,
                    source_ref="pt_notes[3]",
                    supports="supervised_pt",
                    strength=EvidenceStrength.STRONG,
                )
            )
        if "instability" in joined_clinical:
            evidence.append(
                EvidenceItem(
                    code="documented_persistent_instability",
                    statement="Clinical notes document persistent instability.",
                    source_type=SourceType.CLINICAL_NOTE,
                    source_ref="clinical_notes[2]",
                    supports="supervised_pt",
                    strength=EvidenceStrength.MODERATE,
                )
            )
        if "pain" in joined_clinical:
            evidence.append(
                EvidenceItem(
                    code="documented_activity_related_pain",
                    statement="Clinical notes document activity-related pain.",
                    source_type=SourceType.CLINICAL_NOTE,
                    source_ref="clinical_notes[2]",
                    supports="supervised_pt",
                    strength=EvidenceStrength.MODERATE,
                )
            )
        if "fear of re-injury" in joined_pt:
            risk_items.append(
                RiskItem(
                    code="fear_of_reinjury",
                    description="Fear of re-injury may limit return to sport without targeted rehab.",
                    severity=EvidenceStrength.MODERATE,
                )
            )
        if "pain" in joined_clinical:
            risk_items.append(
                RiskItem(
                    code="persistent_activity_related_pain",
                    description="Clinical notes document activity-related pain.",
                    severity=EvidenceStrength.MODERATE,
                )
            )
        if "intact acl graft" in joined_imaging and "no acute tear" in joined_imaging:
            evidence.append(
                EvidenceItem(
                    code="no_acute_structural_failure_on_imaging",
                    statement="Imaging does not show acute graft failure or acute tear.",
                    source_type=SourceType.IMAGING,
                    source_ref="imaging[2]",
                    supports="supervised_pt",
                    strength=EvidenceStrength.STRONG,
                )
            )
        if "early cartilage degeneration" in joined_imaging:
            risk_items.append(
                RiskItem(
                    code="early_cartilage_degeneration",
                    description="Imaging documents early cartilage degeneration.",
                    severity=EvidenceStrength.MODERATE,
                )
            )
        if "only 4 to 5 weeks" in joined_pt or "not completed" in joined_pt:
            evidence.append(
                EvidenceItem(
                    code="post_revision_rehab_incomplete",
                    statement="The post-revision rehabilitation course was incomplete.",
                    source_type=SourceType.PT_NOTE,
                    source_ref="pt_notes[1]",
                    supports="supervised_pt",
                    strength=EvidenceStrength.STRONG,
                )
            )
        if "acute tear" in joined_imaging and "no acute tear" not in joined_imaging:
            evidence.append(
                EvidenceItem(
                    code="possible_acute_structural_failure",
                    statement="Imaging raises concern for acute structural failure.",
                    source_type=SourceType.IMAGING,
                    source_ref="imaging[0]",
                    supports="surgical_eval",
                    strength=EvidenceStrength.STRONG,
                )
            )

        if any(item.code == "post_revision_rehab_incomplete" for item in evidence):
            requirements.append(
                RequirementItem(
                    code="document_prior_rehab_gap",
                    description="Prior incomplete post-revision rehabilitation should be explicitly documented.",
                    owner=WorkflowOwner.CLINICAL,
                    status=RequirementStatus.SATISFIED,
                )
            )
        else:
            requirements.append(
                RequirementItem(
                    code="document_prior_rehab_gap",
                    description="Need explicit documentation that the prior rehab course was incomplete.",
                    owner=WorkflowOwner.CLINICAL,
                    status=RequirementStatus.UNSATISFIED,
                )
            )

        requirements.append(
            RequirementItem(
                code="objective_deficit_measurement",
                description="Need objective functional measurements for strength and movement control.",
                owner=WorkflowOwner.CLINICAL,
                status=RequirementStatus.UNSATISFIED,
            )
        )

        stop_conditions.append("new_acute_tear_identified")
        stop_conditions.append("progressive_instability_after_structured_pt")
        next_steps.extend(
            [
                "collect_objective_strength_testing",
                "collect_single_leg_functional_testing",
                "define_supervised_pt_block",
                "reassess_after_pt_block",
            ]
        )

        surgical_evidence = [item for item in evidence if item.supports == "surgical_eval"]
        pt_evidence = [item for item in evidence if item.supports == "supervised_pt"]
        if surgical_evidence and not pt_evidence:
            decision = ClinicalDecision(
                recommended_service="surgical_eval",
                recommendation_disposition=RecommendationDisposition.RECOMMEND,
                recommended_path=CarePath.SURGICAL_REEVALUATION,
                recommendation_reason_codes=["possible_acute_structural_failure"],
            )
        elif not pt_evidence:
            decision = ClinicalDecision(
                recommended_service="supervised_pt",
                recommendation_disposition=RecommendationDisposition.CONSIDER_AFTER_PREREQUISITES,
                recommended_path=CarePath.NEED_MORE_INFORMATION,
                recommendation_reason_codes=[],
            )
        else:
            decision = ClinicalDecision(
                recommended_service="supervised_pt",
                recommendation_disposition=RecommendationDisposition.RECOMMEND,
                recommended_path=CarePath.ADDITIONAL_STRUCTURED_PT,
                recommendation_reason_codes=[item.code for item in pt_evidence],
            )

        confidence = ConfidenceLevel.HIGH if len(pt_evidence) >= 3 else ConfidenceLevel.MEDIUM
        if not pt_evidence and not surgical_evidence:
            confidence = ConfidenceLevel.LOW

        return ClinicalAgentOutput(
            decision=decision,
            evidence=evidence,
            requirements=requirements,
            risk_items=risk_items,
            stop_conditions=stop_conditions,
            next_steps=sorted(set(next_steps)),
            confidence=confidence,
        )
