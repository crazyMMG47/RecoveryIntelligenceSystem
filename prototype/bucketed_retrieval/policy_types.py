"""
policy_types.py — single source of truth for all shared data classes.

Previously the codebase had both PolicySnippet (kp_policy_fetch.py)
and RetrievedPolicyChunk (targeted_policy_fetcher.py) which were the same
concept with different field names. This unifies them into PolicyChunk.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyPage:
    """A fully fetched and text-extracted policy page or PDF."""
    url: str
    title: str
    text: str
    parent_url: str | None = None
    source_type: str = "html"   # "html" | "pdf"


@dataclass(frozen=True)
class PolicyChunk:
    """
    A single chunk of a PolicyPage, with bucket classification applied.

    chunk_id  — stable hash of (url, section, word_offset)
    source_ref — alias kept for backwards compat with InsuranceAgent consumption
    """
    chunk_id: str
    url: str
    title: str
    section: str | None
    text: str
    bucket: str          # always set; never "unknown"
    parent_url: str | None = None
    source_type: str = "html"

    # Backwards-compat alias used by BucketedPolicyRetriever / InsuranceAgent
    @property
    def source_ref(self) -> str:
        return self.chunk_id

    # Backwards-compat alias: old code read chunk.bucket on RetrievedPolicyChunk
    # which already had it, so no change needed there.