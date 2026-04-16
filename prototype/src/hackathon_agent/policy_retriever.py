from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from schemas import InsuranceAgentInput


@dataclass(frozen=True)
class RetrievedPolicyChunk:
    source_ref: str
    title: str
    text: str
    url: str | None = None


@dataclass(frozen=True)
class PolicyDocument:
    source_ref: str
    title: str
    text: str
    url: str | None = None


class PolicyRetriever:
    """
    Local cached-document retriever for insurance policy RAG.

    Behavior:
    - If payload.policy_text is provided, wrap it directly as a fallback chunk.
    - Otherwise, load cached text files from policy_cache/
    - Chunk the cached documents
    - Score chunks with lightweight keyword matching
    - Return top-k relevant chunks
    """

    def __init__(
        self,
        *,
        cache_dir: str | Path = "policy_cache",
        top_k: int = 4,
        chunk_size_words: int = 450,
        chunk_overlap_words: int = 75,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.top_k = top_k
        self.chunk_size_words = chunk_size_words
        self.chunk_overlap_words = chunk_overlap_words

    def retrieve(self, payload: InsuranceAgentInput) -> list[RetrievedPolicyChunk]:
        # Fallback mode: use provided policy_text directly if present.
        if payload.policy_text:
            return [
                RetrievedPolicyChunk(
                    source_ref="policy_text",
                    title="Provided policy text",
                    text=payload.policy_text.strip(),
                    url=None,
                )
            ]

        documents = self.load_cached_documents()
        if not documents:
            return []

        query = self.build_query(payload)
        chunks = self.chunk_documents(documents)
        ranked = self.rank_chunks(query=query, chunks=chunks)
        return ranked[: self.top_k]

    def load_cached_documents(self) -> list[PolicyDocument]:
        if not self.cache_dir.exists():
            return []

        docs: list[PolicyDocument] = []

        for path in sorted(self.cache_dir.glob("*.txt")):
            raw = path.read_text(encoding="utf-8")
            parsed = self.parse_cached_document(raw, source_ref=path.stem)
            if parsed is not None:
                docs.append(parsed)

        return docs

    def parse_cached_document(
        self,
        raw_text: str,
        *,
        source_ref: str,
    ) -> PolicyDocument | None:
        url_match = re.search(r"^URL:\s*(.+)$", raw_text, flags=re.MULTILINE)
        title_match = re.search(r"^TITLE:\s*(.+)$", raw_text, flags=re.MULTILINE)
        content_match = re.search(r"^CONTENT:\n(.+)$", raw_text, flags=re.MULTILINE | re.DOTALL)

        if not content_match:
            return None

        url = url_match.group(1).strip() if url_match else None
        title = title_match.group(1).strip() if title_match else source_ref
        content = content_match.group(1).strip()

        if not content:
            return None

        return PolicyDocument(
            source_ref=source_ref,
            title=title,
            text=content,
            url=url,
        )

    def build_query(self, payload: InsuranceAgentInput) -> str:
        evidence_codes = " ".join(item.code for item in payload.clinical_evidence)
        clinical_reasons = " ".join(payload.clinical_decision.recommendation_reason_codes)

        pieces = [
            payload.question,
            payload.clinical_decision.recommended_service,
            payload.clinical_decision.recommended_path.value,
            evidence_codes,
            clinical_reasons,
            "physical therapy",
            "outpatient rehab",
            "utilization review",
            "physician justification",
            "objective measurements",
            "therapy plan",
            "medical necessity",
        ]
        return " ".join(piece for piece in pieces if piece).strip().lower()

    def chunk_documents(self, documents: list[PolicyDocument]) -> list[RetrievedPolicyChunk]:
        all_chunks: list[RetrievedPolicyChunk] = []

        for doc in documents:
            section_chunks = self.section_chunk_document(doc)
            if section_chunks:
                all_chunks.extend(section_chunks)
            else:
                all_chunks.extend(self.sliding_window_chunks(doc))

        return all_chunks

    def section_chunk_document(self, doc: PolicyDocument) -> list[RetrievedPolicyChunk]:
        """
        Split by heading-like lines first.
        Falls back to sliding window if sections are too weak.
        """
        lines = [line.rstrip() for line in doc.text.splitlines()]
        if not lines:
            return []

        sections: list[tuple[str, list[str]]] = []
        current_heading = "document_start"
        current_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if self.looks_like_heading(stripped):
                if current_lines:
                    sections.append((current_heading, current_lines))
                current_heading = stripped[:200]
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_heading, current_lines))

        # If we did not get meaningful sections, return empty to trigger fallback.
        if len(sections) <= 1:
            return []

        chunks: list[RetrievedPolicyChunk] = []
        for idx, (heading, section_lines) in enumerate(sections):
            section_text = "\n".join(section_lines).strip()
            if len(section_text.split()) < 40:
                continue

            # Further split large sections with windowed chunking.
            section_doc = PolicyDocument(
                source_ref=doc.source_ref,
                title=f"{doc.title} | {heading}",
                text=section_text,
                url=doc.url,
            )
            subchunks = self.sliding_window_chunks(section_doc, prefix=f"{doc.source_ref}_sec{idx}")
            chunks.extend(subchunks)

        return chunks

    def sliding_window_chunks(
        self,
        doc: PolicyDocument,
        *,
        prefix: str | None = None,
    ) -> list[RetrievedPolicyChunk]:
        words = doc.text.split()
        if not words:
            return []

        chunks: list[RetrievedPolicyChunk] = []
        step = max(1, self.chunk_size_words - self.chunk_overlap_words)
        chunk_prefix = prefix or doc.source_ref

        for i in range(0, len(words), step):
            chunk_words = words[i : i + self.chunk_size_words]
            if not chunk_words:
                continue

            chunk_text = " ".join(chunk_words).strip()
            if len(chunk_text.split()) < 40:
                continue

            chunk_id = len(chunks)
            chunks.append(
                RetrievedPolicyChunk(
                    source_ref=f"{chunk_prefix}_chunk{chunk_id}",
                    title=doc.title,
                    text=chunk_text,
                    url=doc.url,
                )
            )

        return chunks

    def looks_like_heading(self, line: str) -> bool:
        if not line:
            return False
        if len(line) > 120:
            return False
        if line.endswith(":"):
            return True
        if line.startswith("##"):
            return True
        if line.lower() in {
            "principles",
            "process",
            "plan of care",
            "continuation of therapy",
            "discontinuation of therapy",
            "prior authorization",
            "coverage",
            "criteria",
            "background",
            "why it is done",
            "how well it works",
            "risks",
        }:
            return True

        words = line.split()
        if 1 <= len(words) <= 10 and line == line.title():
            return True

        return False

    def rank_chunks(
        self,
        *,
        query: str,
        chunks: list[RetrievedPolicyChunk],
    ) -> list[RetrievedPolicyChunk]:
        query_terms = self.tokenize(query)

        scored: list[tuple[int, RetrievedPolicyChunk]] = []
        for chunk in chunks:
            text = f"{chunk.title} {chunk.text}".lower()
            score = self.score_text(query_terms, text)
            if score > 0:
                scored.append((score, chunk))

        # fallback: if nothing matched, just return first few chunks
        if not scored:
            return chunks[: self.top_k]

        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored]

    def tokenize(self, text: str) -> list[str]:
        tokens = re.findall(r"[a-z0-9_]+", text.lower())
        return [tok for tok in tokens if len(tok) > 2]

    def score_text(self, query_terms: list[str], text: str) -> int:
        score = 0

        # term overlap
        for term in query_terms:
            if term in text:
                score += 1

        # boosted phrases for your insurance use case
        boosted_phrases = [
            "physician justification",
            "objective measurements",
            "functional progress",
            "therapy plan",
            "medical necessity",
            "physical therapy",
            "continuation of therapy",
            "discontinuation of therapy",
            "utilization management",
            "prior authorization",
            "continuity of care",
            "acl",
            "revision",
            "instability",
        ]
        for phrase in boosted_phrases:
            if phrase in text:
                score += 3

        return score