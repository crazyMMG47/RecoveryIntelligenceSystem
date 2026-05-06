from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

from .policy_map import POLICY_MAP
from .policy_router import PolicyRouter
from .schemas import InsuranceAgentInput


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNIPPETS_PATH = ROOT / "data" / "policy_snippets" / "snippets.jsonl"

# Hybrid scoring weights: cosine similarity + normalised keyword score
# Heavily weight keywords to prioritize domain-specific boosts over generic embeddings
# 0.2 cosine allows embeddings to break ties, but 0.8 keyword ensures our boosts dominate
_HYBRID_COSINE_WEIGHT = 0.2
_HYBRID_KEYWORD_WEIGHT = 0.8

# Keyword score threshold below which a chunk is discarded regardless of cosine similarity.
# The noise penalty for bad URLs is -3.0, so -2.0 safely catches those while
# allowing mildly-off-topic chunks to still be rescued by a strong cosine score.
_NOISE_SCORE_THRESHOLD = -2.0

# Generic section headings that contribute little clinical/policy evidence.
# Chunks whose section matches one of these are down-scored by 2.0 in keyword scoring.
_NOISY_SECTIONS: frozenset[str] = frozenset({
    "references",
    "revision history",
    "source policy",
    "document_start",
    "table of contents",
    "acknowledgments",
    "footnotes",
    "appendix",
    "glossary",
})


# ---------------------------------------------------------------------------
# Embedding model
# ---------------------------------------------------------------------------

class EmbeddingModel:
    """Lazy-loading wrapper around sentence-transformers all-MiniLM-L6-v2.

    Imported lazily so the module loads cleanly even before the package is
    installed; the model is only loaded on first actual use.
    """

    MODEL_NAME = "all-MiniLM-L6-v2"
    _instance: EmbeddingModel | None = None

    def __init__(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for embedding retrieval. "
                "Install with: pip install -r requirements.txt\n"
                "Or: pip install sentence-transformers"
            ) from exc
        try:
            self._model = SentenceTransformer(self.MODEL_NAME)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load embedding model '{self.MODEL_NAME}'. "
                f"Error: {exc}\n"
                "Ensure you have internet connectivity and disk space for model download."
            ) from exc

    @classmethod
    def get_default(cls) -> EmbeddingModel:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def encode(self, texts: list[str]) -> np.ndarray:
        import numpy as np

        vecs = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vecs, dtype=np.float32)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

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
    # Maps source_ref → combined hybrid score for each selected chunk.
    # Useful for debugging retrieval quality in run_policy_retriever.py.
    scores: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RoutedSnippetSet:
    domain: str
    candidate_urls: list[str]
    chunks: list[RetrievedPolicyChunk]
    notes: list[str]


# ---------------------------------------------------------------------------
# Bucket definitions
# ---------------------------------------------------------------------------

_BUCKET_DEFINITIONS: dict[str, dict[str, object]] = {
    "coverage_rules": {
        "suffix": (
            "coverage benefit outpatient rehab physical therapy authorization "
            "utilization review criteria visit limits copay deductible visits per year"
        ),
        "boosts": [
            "coverage",
            "benefit",
            "authorization",
            "utilization review",
            "visit",
            "limit",
            "preauthorization",
            "physical therapy",
            "rehabilitation",
            "outpatient",
            "copay",
            "copayment",
            "deductible",
            "visits per year",
        ],
        "related_buckets": {"coverage_rules", "authorization"},
    },
    "medical_necessity": {
        "suffix": (
            "medical necessity continuation objective progress measurable "
            "functional deficits supervised physical therapy rehabilitation "
            "quadriceps strength deficit acl neuromuscular control"
        ),
        "boosts": [
            "medical necessity",
            "objective progress",
            "measurable",
            "functional deficits",
            "continuation of therapy",
            "physical therapy",
            "rehabilitation",
            "quadriceps",
            "strength deficit",
            "acl",
            "neuromuscular",
            "objective strength",
            "functional deficit",
            "acl rehabilitation",
        ],
        "related_buckets": {"medical_necessity", "condition_guideline", "documentation_requirements"},
    },
    "documentation_requirements": {
        "suffix": (
            "documentation physician justification therapy plan frequency "
            "duration reassessment plan of care objective strength quadriceps "
            "neuromuscular functional measurements"
        ),
        "boosts": [
            "physician justification",
            "therapy plan",
            "frequency",
            "duration",
            "documentation",
            "plan of care",
            "measurable assessment",
            "objective strength",
            "objective measurements",
            "quadriceps",
            "neuromuscular",
            "functional movement",
            "structured therapy plan",
        ],
        "related_buckets": {"documentation_requirements", "authorization"},
    },
    "stop_or_escalate": {
        "suffix": (
            "adherence history interrupted attendance denial appeal escalation "
            "reconsideration approval risk incomplete rehabilitation no progress"
        ),
        "boosts": [
            "adherence",
            "attendance",
            "denial",
            "appeal",
            "expedited appeal",
            "reconsideration",
            "incomplete rehabilitation",
            "incomplete rehab",
            "no progress",
            "plateau",
            "escalation",
            "escalate",
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
    "quadriceps weakness",
    "strength deficit",
    "acl protocol",
    "acl rehabilitation",
    "measurable improvement",
    "objective measurements",
    "acl",
    "protocol",
    "return to sport",
    "return-to-sport",
    "strength testing",
    "hop test",
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
    "objective strength",
    "objective measurements",
    "structured therapy plan",
    "quadriceps",
    "neuromuscular",
    "functional movement",
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

# PT-specific chunks to prioritize in retrieval
_PT_CHUNK_WHITELIST = frozenset({
    "pt_med_nec_001",
    "pt_med_nec_002",
    "pt_med_nec_003",
    "pt_doc_req_001",
    "pt_doc_req_002",
    "pt_cov_rules_001",
    "pt_cov_rules_002",
    "pt_risk_escalate_001",
    "pt_risk_incomplete_rehab_001",
})


# ---------------------------------------------------------------------------
# Corpus — loads JSONL and manages the embedding cache
# ---------------------------------------------------------------------------

class PolicySnippetCorpus:
    def __init__(
        self,
        snippets_path: str | Path = DEFAULT_SNIPPETS_PATH,
        *,
        embedding_model: EmbeddingModel | None = None,
    ) -> None:
        self.snippets_path = Path(snippets_path)
        self._embedding_model = embedding_model
        self.chunks = self._load()
        self.embeddings, self._ref_to_idx = self._load_or_build_embeddings()

    # -- JSONL loader --------------------------------------------------------

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

    # -- Embedding cache -----------------------------------------------------

    def _corpus_hash(self) -> str:
        h = hashlib.md5()
        with self.snippets_path.open("rb") as f:
            h.update(f.read())
        return h.hexdigest()

    def _cache_paths(self) -> tuple[Path, Path]:
        parent = self.snippets_path.parent
        stem = self.snippets_path.stem
        return (
            parent / f"{stem}_embeddings.npy",
            parent / f"{stem}_embeddings_hash.txt",
        )

    def _load_or_build_embeddings(self) -> tuple[np.ndarray, dict[str, int]]:
        import numpy as np

        emb_path, hash_path = self._cache_paths()
        current_hash = self._corpus_hash()
        ref_to_idx = {chunk.source_ref: i for i, chunk in enumerate(self.chunks)}

        if emb_path.exists() and hash_path.exists():
            if hash_path.read_text().strip() == current_hash:
                return np.load(str(emb_path)), ref_to_idx

        # Build embeddings from scratch
        model = self._embedding_model or EmbeddingModel.get_default()
        texts = [
            f"{chunk.title} {chunk.section} {chunk.text}"
            for chunk in self.chunks
        ]
        embeddings = model.encode(texts)
        np.save(str(emb_path), embeddings)
        hash_path.write_text(current_hash)

        return embeddings, ref_to_idx

    # -- Subset lookup -------------------------------------------------------

    def get_embeddings_for(self, chunks: list[RetrievedPolicyChunk]) -> np.ndarray:
        """Return embedding matrix for a subset of corpus chunks, shape (n, dim)."""
        import numpy as np

        indices = [self._ref_to_idx[chunk.source_ref] for chunk in chunks]
        return self.embeddings[indices]


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------

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

        # Fetch the embedding sub-matrix for the domain-filtered chunk subset
        # once — reused across all 4 bucket queries.
        chunk_embeddings = self.corpus.get_embeddings_for(routed.chunks)
        model = self.corpus._embedding_model or EmbeddingModel.get_default()

        buckets: list[EvidenceBucket] = []
        for bucket_name, definition in _BUCKET_DEFINITIONS.items():
            query = f"{base_query} {definition['suffix']}"
            query_embedding = model.encode([query])[0]

            ranked: list[tuple[float, RetrievedPolicyChunk]] = []
            if bucket_name != "stop_or_escalate" or self._should_include_stop_or_escalate(base_query):
                ranked = self._rank_chunks(
                    bucket_name=bucket_name,
                    query=query,
                    chunks=routed.chunks,
                    chunk_embeddings=chunk_embeddings,
                    query_embedding=query_embedding,
                    bucket_boosts=list(definition["boosts"]),
                    related_buckets=set(definition["related_buckets"]),
                    candidate_urls=routed.candidate_urls,
                    domain=routed.domain,
                )

            # ranked is [(combined_score, chunk), ...] sorted descending
            ranked_chunks = [chunk for _, chunk in ranked]
            all_scores = {chunk.source_ref: score for score, chunk in ranked}

            selected = self._select_diverse(ranked_chunks, top_k=self.top_k_per_bucket)
            # Re-sort selected chunks by hybrid score descending so the LLM sees
            # the strongest evidence first, regardless of diverse-selection order.
            selected_scores = {c.source_ref: all_scores[c.source_ref] for c in selected}
            selected.sort(key=lambda c: selected_scores[c.source_ref], reverse=True)

            confidence = self._confidence(
                bucket_name=bucket_name,
                chunks=selected,
                candidate_urls=routed.candidate_urls,
                scores=selected_scores,
            )
            buckets.append(
                EvidenceBucket(
                    bucket_name=bucket_name,
                    query=query,
                    chunks=selected,
                    confidence=confidence,
                    notes=routed.notes + self._build_notes(bucket_name, selected, confidence),
                    scores={c.source_ref: all_scores[c.source_ref] for c in selected},
                )
            )

        return buckets

    def flatten(self, buckets: list[EvidenceBucket]) -> list[RetrievedPolicyChunk]:
        flat: list[RetrievedPolicyChunk] = []
        for bucket in buckets:
            flat.extend(bucket.chunks)
        return flat

    # -- Routing -------------------------------------------------------------

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
        raw = " ".join(part for part in parts if part).strip().lower()
        # Deduplicate tokens while preserving order — prevents repetition from
        # clinical codes and reason codes sharing the same terms.
        seen: set[str] = set()
        deduped: list[str] = []
        for token in raw.split():
            if token not in seen:
                seen.add(token)
                deduped.append(token)
        return " ".join(deduped)

    # -- Hybrid ranking ------------------------------------------------------

    def _rank_chunks(
        self,
        *,
        bucket_name: str,
        query: str,
        chunks: list[RetrievedPolicyChunk],
        chunk_embeddings: np.ndarray | None,
        query_embedding: np.ndarray | None,
        bucket_boosts: list[str],
        related_buckets: set[str],
        candidate_urls: list[str],
        domain: str,
    ) -> list[tuple[float, RetrievedPolicyChunk]]:
        query_tokens = set(self._tokenize(query))

        # --- Keyword scores (same signals as before) ---
        keyword_scores: list[float] = []
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

            # Additional PT-specific phrase boosts (higher weight than bucket boosts)
            pt_specific_phrases = [
                "quadriceps weakness",
                "strength deficit",
                "objective strength",
                "functional deficit",
                "acl rehabilitation",
                "structured therapy plan",
                "incomplete rehabilitation",
                "neuromuscular control",
                "acl protocol",
                "pt authorization",
                "pt frequency",
                "pt coverage",
            ]
            for phrase in pt_specific_phrases:
                if phrase in blob:
                    score += 4.0

            if chunk.bucket in related_buckets:
                score += 4.0
            elif chunk.bucket != "other":
                score -= 1.0

            if chunk.url in candidate_urls:
                score += 2.5

            # Boost PT-specific chunk titles/sections when in pt_rehab domain
            if domain == "pt_rehab":
                # Strong priority for PT-specific chunks
                if chunk.source_ref in _PT_CHUNK_WHITELIST:
                    score += 10.0

                # Also boost chunks with PT-specific titles/sections
                pt_title_keywords = [
                    "physical therapy",
                    "pt authorization",
                    "acl",
                    "rehabilitation",
                    "strength",
                    "objective measurements",
                    "neuromuscular",
                ]
                if any(kw in chunk.title.lower() or kw in chunk.section.lower() for kw in pt_title_keywords):
                    score += 5.0

            # Penalize generic priorauth chunks when looking for PT-specific content
            if (
                domain == "pt_rehab"
                and bucket_name in ("medical_necessity", "documentation_requirements")
                and "priorauth" in chunk.url.lower()
                and not any(
                    phrase in blob
                    for phrase in [
                        "physical therapy",
                        "acl",
                        "quadriceps",
                        "objective strength",
                        "neuromuscular",
                    ]
                )
            ):
                score -= 3.0

            if domain == "pt_rehab" and any(
                phrase in blob
                for phrase in [
                    "physical therapy",
                    "rehabilitation",
                    "plan of care",
                    "medical necessity",
                    "acl",
                    "knee",
                    "quadriceps",
                    "strength",
                    "neuromuscular",
                    "objective measurements",
                    "functional deficit",
                ]
            ):
                score += 3.0

            if any(noise in chunk.url.lower() for noise in ["mri-knee", "radiology"]):
                score -= 3.0

            # Penalise generic/structural sections with little policy substance
            if any(ns in chunk.section.lower() for ns in _NOISY_SECTIONS):
                score -= 2.0

            keyword_scores.append(score)

        # --- Cosine similarities ---
        if chunk_embeddings is not None and query_embedding is not None:
            raw_cosine = (chunk_embeddings @ query_embedding).tolist()
            cosine_sims: list[float] = [max(0.0, float(s)) for s in raw_cosine]
        else:
            cosine_sims = [0.0] * len(chunks)

        # --- Combine ---
        # Normalise keyword scores so both components live in [0, 1].
        max_kw = max((s for s in keyword_scores if s > 0), default=1.0)

        scored: list[tuple[float, RetrievedPolicyChunk]] = []
        for chunk, kw_score, cos_sim in zip(chunks, keyword_scores, cosine_sims):
            # Hard-discard strongly noisy chunks — a high cosine score on a
            # completely irrelevant URL (e.g. radiology) should not override
            # the explicit noise penalty.
            if kw_score <= _NOISE_SCORE_THRESHOLD:
                continue

            norm_kw = max(0.0, kw_score) / max_kw
            combined = _HYBRID_COSINE_WEIGHT * cos_sim + _HYBRID_KEYWORD_WEIGHT * norm_kw

            if combined > 0:
                scored.append((combined, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return scored

    # -- Selection and scoring -----------------------------------------------

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
            # For PT domain, also accept condition_guideline chunks (e.g. ACL protocols)
            # that have PT anchors and medical necessity keywords
            return has_pt_anchor and self._has_any(blob, _MEDICAL_NECESSITY_ANCHORS)
        if bucket_name == "documentation_requirements":
            return (has_pt_anchor or "physical therapy established plan" in blob) and self._has_any(
                blob,
                _DOCUMENTATION_ANCHORS,
            )
        if bucket_name == "stop_or_escalate":
            return self._has_any(blob, _STOP_OR_ESCALATE_TRIGGERS)

        # Boost condition_guideline bucket for PT domain (includes ACL rehab protocols)
        if bucket_name == "condition_guideline" and domain == "pt_rehab":
            return has_pt_anchor

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
        scores: dict[str, float] | None = None,
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

        # Bucket-specific anchor boosts
        if bucket_name == "coverage_rules" and self._has_any(joined, _COVERAGE_ANCHORS):
            score += 0.15
        if bucket_name == "medical_necessity" and self._has_any(joined, _MEDICAL_NECESSITY_ANCHORS):
            score += 0.20
        if bucket_name == "documentation_requirements" and self._has_any(joined, _DOCUMENTATION_ANCHORS):
            score += 0.20
        if bucket_name == "stop_or_escalate" and self._has_any(joined, _STOP_OR_ESCALATE_TRIGGERS):
            score += 0.10

        # Discount when best hybrid score is weak — overconfident buckets mislead the LLM.
        if scores:
            best = max(scores.values(), default=0.0)
            if best < 0.30:
                score *= 0.70
            elif best < 0.50:
                score *= 0.85

        # Penalise when most chunks are generic/structural sections.
        noisy_count = sum(
            1 for chunk in chunks
            if any(ns in chunk.section.lower() for ns in _NOISY_SECTIONS)
        )
        if chunks and noisy_count > len(chunks) // 2:
            score *= 0.80

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
