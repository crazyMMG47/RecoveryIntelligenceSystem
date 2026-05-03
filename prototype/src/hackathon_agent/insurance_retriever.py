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

_PT_REHAB_ANCHORS = [
    "physical therapy",
    "physiotherapy",
    "rehabilitation",
    "outpatient therapy",
    "occupational and physical therapy",
]

_COVERAGE_ANCHORS = [
    "coverage",
    "covered",
    "benefit",
    "authorization",
    "preauthorization",
    "prior authorization",
    "visit",
    "visits",
    "limit",
    "limits",
]

_MEDICAL_NECESSITY_ANCHORS = [
    "medical necessity",
    "medically necessary",
    "musculoskeletal",
    "neuromuscular",
    "functional",
    "function",
    "movement dysfunction",
    "improve function",
]

_DOCUMENTATION_ANCHORS = [
    "written treatment plan",
    "plan of care",
    "quantitative outcome measures",
    "objective",
    "standardized tests",
    "measurable assessment",
    "frequency",
    "duration",
    "goals",
    "documentation",
]

_STOP_OR_ESCALATE_TRIGGERS = [
    "adherence",
    "attendance",
    "appeal",
    "denial",
    "denied",
    "interrupted",
    "noncoverage",
    "non-covered",
    "reconsideration",
    "retroactive",
]


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
            ranked: list[RetrievedPolicyChunk] = []
            if bucket_name != "stop_or_escalate" or self._should_include_stop_or_escalate(base_query):
                ranked = self._rank_chunks(
                    bucket_name=bucket_name,
                    query=query,
                    chunks=routed.chunks,
                    bucket_boosts=list(definition["boosts"]),
                    related_buckets=set(definition["related_buckets"]),
                    candidate_urls=routed.candidate_urls,
                    domain=routed.domain,
                )
            selected = self._select_diverse(ranked, top_k=self.top_k_per_bucket)
            confidence = self._confidence(
                bucket_name=bucket_name,
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
        bucket_name: str,
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
            if not self._chunk_matches_bucket(
                bucket_name=bucket_name,
                blob=blob,
                domain=domain,
            ):
                continue

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

    def _chunk_matches_bucket(
        self,
        *,
        bucket_name: str,
        blob: str,
        domain: str,
    ) -> bool:
        if domain != "pt_rehab":
            return True

        has_pt_anchor = self._has_any(blob, _PT_REHAB_ANCHORS)

        if bucket_name == "coverage_rules":
            return has_pt_anchor and self._has_any(blob, _COVERAGE_ANCHORS)
        if bucket_name == "medical_necessity":
            if (
                "specifically excluded under many benefit plans" in blob
                or "considered not medically necessary" in blob
            ):
                return False
            return has_pt_anchor and self._has_any(blob, _MEDICAL_NECESSITY_ANCHORS)
        if bucket_name == "documentation_requirements":
            return (has_pt_anchor or "physical therapy established plan" in blob) and self._has_any(
                blob,
                _DOCUMENTATION_ANCHORS,
            )
        if bucket_name == "stop_or_escalate":
            return self._has_any(blob, _STOP_OR_ESCALATE_TRIGGERS)

        return True

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
        bucket_name: str,
        chunks: list[RetrievedPolicyChunk],
        candidate_urls: list[str],
    ) -> float:
        if not chunks:
            return 0.0

        joined = " ".join(
            f"{chunk.title} {chunk.section} {chunk.text}".lower()
            for chunk in chunks
        )
        score = 0.25 + min(0.30, len(chunks) * 0.10)
        unique_urls = len({chunk.url for chunk in chunks})
        if unique_urls >= 2:
            score += 0.10
        if any(chunk.url in candidate_urls for chunk in chunks):
            score += 0.05

        if bucket_name == "coverage_rules" and self._has_any(joined, _COVERAGE_ANCHORS):
            score += 0.15
        if bucket_name == "medical_necessity" and self._has_any(joined, _MEDICAL_NECESSITY_ANCHORS):
            score += 0.20
        if bucket_name == "documentation_requirements" and self._has_any(joined, _DOCUMENTATION_ANCHORS):
            score += 0.20
        if bucket_name == "stop_or_escalate" and self._has_any(joined, _STOP_OR_ESCALATE_TRIGGERS):
            score += 0.10

        cap = 0.85
        if unique_urls == 1:
            cap = 0.75
        if bucket_name == "stop_or_escalate":
            cap = 0.70

        return min(score, cap)

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

    def _has_any(self, text: str, terms: list[str]) -> bool:
        return any(term in text for term in terms)

    def _should_include_stop_or_escalate(self, base_query: str) -> bool:
        return self._has_any(base_query, _STOP_OR_ESCALATE_TRIGGERS)
