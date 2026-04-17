"""
bucketed_policy_retriever.py

Orchestrates the full retrieval pipeline for the InsuranceAgent:
  route → fetch+filter → rank → assemble EvidenceBuckets.

The heavy lifting (domain filtering, chunking, bucket inference) is now all
in policy_fetcher.py. This class is intentionally thin.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.hackathon_agent.schemas import InsuranceAgentInput
from policy_types import PolicyChunk
from policy_fetcher import PolicyFetcher
from policy_router import PolicyRouter, RoutedPolicyPlan
from policy_map import POLICY_MAP


# ── Evidence bucket (public API consumed by InsuranceAgent) ───────────────────

@dataclass(frozen=True)
class EvidenceBucket:
    bucket_name: str
    query: str
    chunks: list[PolicyChunk]
    confidence: float
    notes: list[str]


# ── Which evidence buckets the InsuranceAgent wants ───────────────────────────
# Each bucket gets its own query string and set of boost phrases used during
# ranking. The bucket names here are the ones the LLM prompt references.

_BUCKET_DEFINITIONS: dict[str, dict] = {
    "coverage_rules": {
        "suffix": (
            "coverage benefit outpatient rehab physical therapy "
            "authorization utilization management criteria"
        ),
        "boosts": [
            "coverage", "benefit", "authorization",
            "utilization management", "criteria", "service",
        ],
        "related_inferred_buckets": {"authorization", "coverage_rules"},
    },
    "medical_necessity": {
        "suffix": (
            "medical necessity measurable improvement objective progress "
            "continuation therapy skilled provider"
        ),
        "boosts": [
            "medical necessity", "measurable improvement",
            "objective progress", "continuation of therapy", "skilled provider",
        ],
        "related_inferred_buckets": {"medical_necessity"},
    },
    "documentation_requirements": {
        "suffix": (
            "documentation plan of care quantitative goals frequency duration "
            "re-evaluation physician justification"
        ),
        "boosts": [
            "documentation", "plan of care", "goals",
            "frequency", "duration", "re-evaluation", "must include",
        ],
        "related_inferred_buckets": {"documentation_requirements"},
    },
    "stop_or_escalate": {
        "suffix": (
            "discontinuation poor attendance compliance home program "
            "continuity of care referral authorization benefit maximum "
            "appeal denial"
        ),
        "boosts": [
            "discontinuation of therapy", "poor attendance", "compliance",
            "continuity of care", "referral", "appeal", "denial",
        ],
        "related_inferred_buckets": {
            "appeals", "authorization", "medical_necessity",
        },
    },
}


# ── Main class ────────────────────────────────────────────────────────────────

class BucketedPolicyRetriever:

    def __init__(
        self,
        *,
        top_k_per_bucket: int = 3,
        verbose: bool = False,
    ) -> None:
        self.top_k_per_bucket = top_k_per_bucket
        self.router = PolicyRouter(POLICY_MAP)
        self.fetcher = PolicyFetcher(verbose=verbose)

    # ── Public entry point ────────────────────────────────────────────────────

    def retrieve(self, payload: InsuranceAgentInput) -> list[EvidenceBucket]:
        """Return one EvidenceBucket per defined bucket category."""

        # Fast-path: inline policy text provided
        if payload.policy_text:
            return self._buckets_from_inline_text(payload.policy_text)

        route: RoutedPolicyPlan = self.router.route(payload)

        # Fetch, domain-filter, and chunk in one call
        all_chunks = self.fetcher.fetch_and_chunk(
            candidate_urls=route.candidate_urls,
            domain=route.domain,
            intents=route.intents,
        )

        if not all_chunks:
            return []

        base_query = self._build_base_query(payload)
        buckets: list[EvidenceBucket] = []

        for bucket_name, defn in _BUCKET_DEFINITIONS.items():
            query = f"{base_query} {defn['suffix']}"
            ranked = self._rank_chunks(
                query=query,
                chunks=all_chunks,
                bucket_boosts=defn["boosts"],
                related_buckets=defn["related_inferred_buckets"],
            )
            selected = self._select_diverse(ranked, top_k=self.top_k_per_bucket)
            confidence = self._confidence(selected, route.domain)

            notes = list(route.notes)
            notes += self._build_notes(bucket_name, selected, confidence)

            buckets.append(
                EvidenceBucket(
                    bucket_name=bucket_name,
                    query=query,
                    chunks=selected,
                    confidence=confidence,
                    notes=notes,
                )
            )

        return buckets

    def flatten(self, buckets: list[EvidenceBucket]) -> list[PolicyChunk]:
        """Return all chunks across all buckets (may have duplicates)."""
        flat: list[PolicyChunk] = []
        for b in buckets:
            flat.extend(b.chunks)
        return flat

    # ── Inline policy text fast-path ──────────────────────────────────────────

    def _buckets_from_inline_text(self, policy_text: str) -> list[EvidenceBucket]:
        chunk = PolicyChunk(
            chunk_id="inline_0",
            url="",
            title="Provided policy text",
            section="provided_policy_text",
            text=policy_text.strip(),
            bucket="provided_policy_text",
            source_type="inline",
        )
        return [
            EvidenceBucket(
                bucket_name="provided_policy_text",
                query="provided policy text",
                chunks=[chunk],
                confidence=1.0,
                notes=["Using directly provided policy text."],
            )
        ]

    # ── Query construction ────────────────────────────────────────────────────

    def _build_base_query(self, payload: InsuranceAgentInput) -> str:
        parts = [
            payload.question,
            payload.clinical_decision.recommended_service,
            payload.clinical_decision.recommended_path.value,
            " ".join(i.code for i in payload.clinical_evidence),
            " ".join(payload.clinical_decision.recommendation_reason_codes),
            "acl revision instability physical therapy kaiser",
        ]
        return " ".join(p for p in parts if p).strip().lower()

    # ── Ranking ───────────────────────────────────────────────────────────────

    def _tokenize(self, text: str) -> list[str]:
        tokens = re.findall(r"[a-z0-9_]+", text.lower())
        return [t for t in tokens if len(t) > 2]

    def _rank_chunks(
        self,
        *,
        query: str,
        chunks: list[PolicyChunk],
        bucket_boosts: list[str],
        related_buckets: set[str],
    ) -> list[PolicyChunk]:
        query_tokens = set(self._tokenize(query))

        scored: list[tuple[float, PolicyChunk]] = []
        for chunk in chunks:
            blob = f"{chunk.title} {chunk.section or ''} {chunk.text}".lower()
            score = 0.0

            # Term overlap with query
            for tok in query_tokens:
                if tok in blob:
                    score += 1.0

            # Bucket-specific phrase boosts
            for phrase in bucket_boosts:
                if phrase in blob:
                    score += 3.0

            # Boost chunks whose inferred bucket matches this evidence bucket
            if chunk.bucket in related_buckets:
                score += 4.0
            elif chunk.bucket and related_buckets and chunk.bucket not in related_buckets:
                score -= 1.5

            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored]

    # ── Diversity selection ───────────────────────────────────────────────────

    def _select_diverse(
        self,
        ranked: list[PolicyChunk],
        *,
        top_k: int,
    ) -> list[PolicyChunk]:
        """Pick top-k chunks, deduping by (url, section) signature."""
        selected: list[PolicyChunk] = []
        seen: set[tuple[str | None, str | None]] = set()

        for chunk in ranked:
            sig = (chunk.url, chunk.section)
            if sig in seen:
                continue
            seen.add(sig)
            selected.append(chunk)
            if len(selected) >= top_k:
                break

        return selected

    # ── Confidence scoring ────────────────────────────────────────────────────

    def _confidence(self, chunks: list[PolicyChunk], domain: str) -> float:
        if not chunks:
            return 0.0

        score = 0.0
        score += min(0.60, len(chunks) * 0.20)   # up to 0.60 for 3+ chunks

        unique_urls = len({c.url for c in chunks if c.url})
        if unique_urls >= 2:
            score += 0.15

        joined = " ".join(c.text.lower() for c in chunks)
        if any(x in joined for x in ["must", "required", "shall", "documentation"]):
            score += 0.10

        if domain == "pt_rehab":
            pt_hits = sum(
                1 for x in [
                    "physical therapy", "rehab", "acl", "knee",
                    "plan of care", "medical necessity",
                ] if x in joined
            )
            score += min(0.15, pt_hits * 0.03)

            noise_hits = sum(
                1 for x in [
                    "mental health", "pharmacy", "autism",
                    "injectable", "transplant",
                ] if x in joined
            )
            score -= min(0.30, noise_hits * 0.10)

        return max(0.0, min(score, 1.0))

    # ── Notes ─────────────────────────────────────────────────────────────────

    def _build_notes(
        self,
        bucket_name: str,
        chunks: list[PolicyChunk],
        confidence: float,
    ) -> list[str]:
        if not chunks:
            return [f"No evidence for bucket '{bucket_name}'."]

        notes = [
            f"{len(chunks)} chunk(s) for '{bucket_name}'. "
            f"Confidence: {confidence:.2f}.",
        ]
        buckets_seen = sorted({c.bucket for c in chunks if c.bucket})
        if buckets_seen:
            notes.append(f"Inferred buckets represented: {', '.join(buckets_seen)}")

        if confidence < 0.50:
            notes.append("Evidence is weak — review manually.")
        elif confidence < 0.80:
            notes.append("Evidence is usable but not definitive.")
        else:
            notes.append("Evidence is strong.")

        return notes