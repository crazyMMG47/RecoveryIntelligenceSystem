from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .policy_map import POLICY_MAP
from .policy_router import PolicyRouter
from .schemas import InsuranceAgentInput


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNIPPETS_PATH = ROOT / "data" / "policy_snippets" / "snippets.jsonl"


@dataclass(frozen=True)
class RetrievedPolicyChunk:
    source_ref: str
    title: str
    section: str
    text: str
    bucket: str
    url: str
    source_type: str


@dataclass(frozen=True)
class EvidenceBucket:
    bucket_name: str
    query: str
    chunks: list[RetrievedPolicyChunk]
    confidence: float
    notes: list[str]


@dataclass(frozen=True)
class RoutedSnippetSet:
    domain: str
    candidate_urls: list[str]
    chunks: list[RetrievedPolicyChunk]
    notes: list[str]


_BUCKET_DEFINITIONS: dict[str, dict[str, object]] = {
    "coverage_rules": {
        "suffix": (
            "coverage benefit outpatient rehab physical therapy authorization "
            "utilization review criteria visit limits"
        ),
        "boosts": [
            "coverage",
            "benefit",
            "authorization",
            "utilization review",
            "visit",
            "limit",
            "preauthorization",
        ],
        "related_buckets": {"coverage_rules", "authorization"},
    },
    "medical_necessity": {
        "suffix": (
            "medical necessity continuation objective progress measurable "
            "functional deficits supervised physical therapy rehabilitation"
        ),
        "boosts": [
            "medical necessity",
            "objective progress",
            "measurable",
            "functional deficits",
            "continuation of therapy",
            "physical therapy",
            "rehabilitation",
        ],
        "related_buckets": {"medical_necessity", "condition_guideline"},
    },
    "documentation_requirements": {
        "suffix": (
            "documentation physician justification therapy plan frequency "
            "duration reassessment plan of care"
        ),
        "boosts": [
            "physician justification",
            "therapy plan",
            "frequency",
            "duration",
            "documentation",
            "plan of care",
            "measurable assessment",
        ],
        "related_buckets": {"documentation_requirements", "authorization"},
    },
    "stop_or_escalate": {
        "suffix": (
            "adherence history interrupted attendance denial appeal escalation "
            "reconsideration approval risk"
        ),
        "boosts": [
            "adherence",
            "attendance",
            "denial",
            "appeal",
            "expedited appeal",
            "reconsideration",
        ],
        "related_buckets": {"stop_or_escalate", "appeals", "authorization"},
    },
}

_URL_POSITIVE: dict[str, list[str]] = {
    "pt_rehab": [
        "physical-therapy",
        "rehab",
        "clinical-review",
        "priorauth",
        "prior-auth",
        "records-standards",
        "documentation",
        "medical-necessity",
        "outpatient",
        "orthopedic",
        "acl-protocol",
    ],
}

_URL_NEGATIVE: dict[str, list[str]] = {
    "pt_rehab": [
        "pharmacy",
        "mental-health",
        "behavioral",
        "radiology",
        "mri-knee",
        "injectable",
        "transplant",
        "autism",
    ],
}

_CONTENT_POSITIVE: dict[str, list[str]] = {
    "pt_rehab": [
        "physical therapy",
        "rehabilitation",
        "plan of care",
        "outpatient therapy",
        "acl",
        "knee",
        "orthopedic",
        "musculoskeletal",
        "medical necessity",
        "authorization",
        "continuation of therapy",
        "documentation",
        "neuromuscular",
        "quadriceps",
    ],
}


class PolicySnippetCorpus:
    def __init__(self, snippets_path: str | Path = DEFAULT_SNIPPETS_PATH) -> None:
        self.snippets_path = Path(snippets_path)
        self.chunks = self._load()

    def _load(self) -> list[RetrievedPolicyChunk]:
        if not self.snippets_path.exists():
            raise RuntimeError(
                f"Policy snippet corpus not found at {self.snippets_path}. "
                "Expected a JSONL corpus built from Kaiser policy sources."
            )

        chunks: list[RetrievedPolicyChunk] = []
        with self.snippets_path.open("r", encoding="utf-8") as handle:
            for line_no, raw_line in enumerate(handle, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                record = json.loads(line)
                text = str(record.get("text", "")).strip()
                if not text:
                    continue
                chunks.append(
                    RetrievedPolicyChunk(
                        source_ref=str(record.get("chunk_id", f"chunk_{line_no}")),
                        title=str(record.get("title", "")).strip() or "Policy snippet",
                        section=str(record.get("section", "")).strip() or "document_start",
                        text=text,
                        bucket=str(record.get("bucket", "other")).strip() or "other",
                        url=str(record.get("url", "")).strip(),
                        source_type=str(record.get("source_type", "jsonl")).strip() or "jsonl",
                    )
                )

        if not chunks:
            raise RuntimeError(f"Policy snippet corpus is empty: {self.snippets_path}")

        return chunks


class InsurancePolicyRetriever:
    def __init__(
        self,
        *,
        top_k_per_bucket: int = 3,
        snippets_path: str | Path = DEFAULT_SNIPPETS_PATH,
    ) -> None:
        self.top_k_per_bucket = top_k_per_bucket
        self.router = PolicyRouter(POLICY_MAP)
        self.corpus = PolicySnippetCorpus(snippets_path)

    def retrieve(self, payload: InsuranceAgentInput) -> list[EvidenceBucket]:
        routed = self._route_chunks(payload)
        base_query = self._build_base_query(payload)
        buckets: list[EvidenceBucket] = []

        for bucket_name, definition in _BUCKET_DEFINITIONS.items():
            query = f"{base_query} {definition['suffix']}"
            ranked = self._rank_chunks(
                query=query,
                chunks=routed.chunks,
                bucket_boosts=list(definition["boosts"]),
                related_buckets=set(definition["related_buckets"]),
                candidate_urls=routed.candidate_urls,
                domain=routed.domain,
            )
            selected = self._select_diverse(ranked, top_k=self.top_k_per_bucket)
            confidence = self._confidence(
                chunks=selected,
                candidate_urls=routed.candidate_urls,
            )
            buckets.append(
                EvidenceBucket(
                    bucket_name=bucket_name,
                    query=query,
                    chunks=selected,
                    confidence=confidence,
                    notes=routed.notes + self._build_notes(bucket_name, selected, confidence),
                )
            )

        return buckets

    def flatten(self, buckets: list[EvidenceBucket]) -> list[RetrievedPolicyChunk]:
        flat: list[RetrievedPolicyChunk] = []
        for bucket in buckets:
            flat.extend(bucket.chunks)
        return flat

    def _route_chunks(self, payload: InsuranceAgentInput) -> RoutedSnippetSet:
        route = self.router.route(payload)
        filtered = [
            chunk
            for chunk in self.corpus.chunks
            if self._chunk_matches_domain(chunk, route.domain)
        ]

        if not filtered:
            raise RuntimeError(f"No policy snippets matched routed domain '{route.domain}'.")

        return RoutedSnippetSet(
            domain=route.domain,
            candidate_urls=route.candidate_urls,
            chunks=filtered,
            notes=route.notes + [f"Snippet corpus candidates: {len(filtered)}"],
        )

    def _chunk_matches_domain(self, chunk: RetrievedPolicyChunk, domain: str) -> bool:
        if domain not in _URL_POSITIVE:
            return True

        url_lower = chunk.url.lower()
        if any(term in url_lower for term in _URL_NEGATIVE.get(domain, [])):
            return False

        if any(term in url_lower for term in _URL_POSITIVE.get(domain, [])):
            return True

        blob = f"{chunk.title} {chunk.section} {chunk.text[:800]}".lower()
        positives = _CONTENT_POSITIVE.get(domain, [])
        hits = sum(1 for term in positives if term in blob)
        return hits >= 2

    def _build_base_query(self, payload: InsuranceAgentInput) -> str:
        parts = [
            payload.question,
            payload.clinical_decision.recommended_service,
            payload.clinical_decision.recommended_path.value,
            " ".join(item.code for item in payload.clinical_evidence),
            " ".join(payload.clinical_decision.recommendation_reason_codes),
            " ".join(item.description for item in payload.clinical_requirements),
        ]
        return " ".join(part for part in parts if part).strip().lower()

    def _rank_chunks(
        self,
        *,
        query: str,
        chunks: list[RetrievedPolicyChunk],
        bucket_boosts: list[str],
        related_buckets: set[str],
        candidate_urls: list[str],
        domain: str,
    ) -> list[RetrievedPolicyChunk]:
        query_tokens = set(self._tokenize(query))
        scored: list[tuple[float, RetrievedPolicyChunk]] = []

        for chunk in chunks:
            blob = f"{chunk.title} {chunk.section} {chunk.text}".lower()
            score = 0.0

            for token in query_tokens:
                if token in blob:
                    score += 1.0

            for phrase in bucket_boosts:
                if phrase in blob:
                    score += 3.0

            if chunk.bucket in related_buckets:
                score += 4.0
            elif chunk.bucket != "other":
                score -= 1.0

            if chunk.url in candidate_urls:
                score += 2.5

            if domain == "pt_rehab" and any(
                phrase in blob
                for phrase in [
                    "physical therapy",
                    "rehabilitation",
                    "plan of care",
                    "medical necessity",
                    "acl",
                    "knee",
                ]
            ):
                score += 1.0

            if any(noise in chunk.url.lower() for noise in ["mri-knee", "radiology"]):
                score -= 3.0

            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored]

    def _select_diverse(
        self,
        ranked: list[RetrievedPolicyChunk],
        *,
        top_k: int,
    ) -> list[RetrievedPolicyChunk]:
        selected: list[RetrievedPolicyChunk] = []
        seen: set[tuple[str, str]] = set()

        for chunk in ranked:
            signature = (chunk.url, chunk.section)
            if signature in seen:
                continue
            seen.add(signature)
            selected.append(chunk)
            if len(selected) >= top_k:
                break

        return selected

    def _confidence(
        self,
        *,
        chunks: list[RetrievedPolicyChunk],
        candidate_urls: list[str],
    ) -> float:
        if not chunks:
            return 0.0

        score = min(0.60, len(chunks) * 0.20)
        unique_urls = len({chunk.url for chunk in chunks})
        if unique_urls >= 2:
            score += 0.15
        if any(chunk.url in candidate_urls for chunk in chunks):
            score += 0.10

        joined = " ".join(chunk.text.lower() for chunk in chunks)
        if any(term in joined for term in ["must", "required", "authorization", "documentation"]):
            score += 0.10
        if any(term in joined for term in ["appeal", "denial", "reconsideration"]):
            score += 0.05

        return min(score, 0.95)

    def _build_notes(
        self,
        bucket_name: str,
        chunks: list[RetrievedPolicyChunk],
        confidence: float,
    ) -> list[str]:
        if not chunks:
            return [f"No policy evidence retrieved for bucket '{bucket_name}'."]

        urls = sorted({chunk.url for chunk in chunks})
        return [
            f"Retrieved {len(chunks)} chunk(s) for '{bucket_name}'.",
            f"Bucket confidence: {confidence:.2f}.",
            f"Source URLs represented: {len(urls)}.",
        ]

    def _tokenize(self, text: str) -> list[str]:
        tokens = re.findall(r"[a-z0-9_]+", text.lower())
        return [token for token in tokens if len(token) > 2]
