"""
policy_domain_filter.py — page-level and section-level relevance gates.

This module is the primary fix for the "unrelated docs getting through" problem.
It is applied at TWO distinct points in the pipeline:

  1. PAGE LEVEL  (policy_fetcher.py)
     Called immediately after a page is fetched, before it is chunked at all.
     A page that fails this check is discarded entirely — no chunks produced.

  2. SECTION LEVEL  (policy_fetcher.py, inside split_page_into_sections)
     Called for each section inside a page that already passed the page-level
     check. Skips sections that are clearly off-topic (e.g. a PT-rehab page
     that has a short aside about pharmacy benefits).

Decision logic (page level):
  a. URL path hard-block  — if the URL contains a known negative path term,
     immediately discard regardless of content.
  b. URL path fast-pass   — if the URL contains a known positive path term,
     immediately keep without reading content.
  c. Content fallback     — read the title + first ~400 words. If any strong
     negative phrase is found, discard. Otherwise require ≥2 positive hits.

Why URL-first?
  The URL path is a reliable, cheap signal that doesn't require reading the
  document body. "physical-therapy" in the path means the page is about PT;
  "pharmacy" in the path means it is not. Using URL signals first also avoids
  the expensive re-fetch that the previous child-link scorer did.
"""

from __future__ import annotations

# ── per-domain URL path signals ────────────────────────────────────────────────
# These are matched against the lowercase URL string.

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
        "musculoskeletal",
    ],
    "claims": [
        "claims", "billing", "reconsideration",
    ],
    "mental_health": [
        "mental-health", "behavioral", "psychiatric",
    ],
    "pharmacy": [
        "pharmacy", "drug", "injectable", "formulary",
    ],
}

_URL_NEGATIVE: dict[str, list[str]] = {
    "pt_rehab": [
        "pharmacy", "mental-health", "behavioral",
        "dental", "vision", "transplant", "radiology",
        "substance-abuse", "injectable", "autism",
        "gender", "chiropractic", "infusion",
        "dermatology", "bariatric", "acupuncture",
    ],
}

# ── per-domain content signals ─────────────────────────────────────────────────

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
        "clinical review",
        "continuation of therapy",
        "documentation requirements",
        "skilled therapy",
        "neuromuscular",
        "quadriceps",
        "prior authorization",
    ],
}

# A SINGLE match on any of these in title + first 400 words → discard page.
# Keep this list tight; false positives here mean lost evidence.
_CONTENT_NEGATIVE_HARD: dict[str, list[str]] = {
    "pt_rehab": [
        "mental health services",
        "behavioral health",
        "drug formulary",
        "pharmacy benefit",
        "autism spectrum",
        "gender dysphoria",
        "organ transplant",
        "injectable medication",
        "infusion therapy",
        "substance abuse treatment",
        "chiropractic services",
        "vision care benefit",
        "dental benefit",
    ],
}

_MIN_POSITIVE_HITS_FOR_CONTENT_PASS = 2


def page_is_relevant(
    *,
    url: str,
    title: str,
    text: str,
    domain: str,
) -> bool:
    """
    Returns True if this page should be kept for the given domain.

    Called BEFORE chunking — if False the page is silently dropped and
    no chunks are produced for it.
    """
    # Unknown domain: keep everything so we don't silently lose evidence.
    if domain not in _URL_POSITIVE and domain not in _CONTENT_POSITIVE:
        return True

    url_l = url.lower()

    # ── a. Hard-block on negative URL path ────────────────────────────────────
    for term in _URL_NEGATIVE.get(domain, []):
        if term in url_l:
            return False

    # ── b. Fast-pass on positive URL path ─────────────────────────────────────
    for term in _URL_POSITIVE.get(domain, []):
        if term in url_l:
            return True

    # ── c. Content fallback (title + first ~400 words) ────────────────────────
    # Using ~400 words keeps this cheap; the "about this page" information
    # is almost always in the first paragraph or two.
    sample_words = text.split()[:400]
    blob = f"{title.lower()} {' '.join(sample_words).lower()}"

    for phrase in _CONTENT_NEGATIVE_HARD.get(domain, []):
        if phrase in blob:
            return False

    pos_hits = sum(
        1 for phrase in _CONTENT_POSITIVE.get(domain, []) if phrase in blob
    )
    return pos_hits >= _MIN_POSITIVE_HITS_FOR_CONTENT_PASS


def section_is_relevant(
    *,
    heading: str,
    text: str,
    domain: str,
) -> bool:
    """
    Section-level guard applied inside pages that already passed page_is_relevant.

    More permissive than the page-level check — it only discards sections
    where a hard-negative phrase appears, since the page has already been
    validated as broadly on-topic.
    """
    if domain not in _CONTENT_NEGATIVE_HARD:
        return True

    # Skip very short sections (< 40 words) — not worth scoring.
    if len(text.split()) < 40:
        return False

    blob = f"{heading.lower()} {text[:800].lower()}"

    for phrase in _CONTENT_NEGATIVE_HARD.get(domain, []):
        if phrase in blob:
            return False

    return True


def score_child_link(
    *,
    link_text: str,
    href: str,
    domain: str,
    intents: list[str],
) -> float:
    """
    Score a candidate child link URL. Positive = worth following.

    Strategy: URL path signals first (free), then link text (cheap).
    This replaces the previous approach that re-fetched HTML just to score links.
    """
    score = 0.0
    href_l = href.lower()
    link_l = link_text.lower()

    # Hard block on known-irrelevant URL paths
    for term in _URL_NEGATIVE.get(domain, []):
        if term in href_l:
            return -1.0  # caller should skip

    # URL path positive match — strong signal
    for term in _URL_POSITIVE.get(domain, []):
        if term in href_l:
            score += 4.0

    # Link text positive match — moderate signal
    link_positive = _CONTENT_POSITIVE.get(domain, [])
    for phrase in link_positive:
        if phrase in link_l:
            score += 2.0

    # Intent-specific boosts
    intent_terms: dict[str, list[str]] = {
        "authorization": ["authorization", "priorauth", "prior-auth", "coverage"],
        "documentation": ["documentation", "records", "plan-of-care"],
        "medical_necessity": ["medical-necessity", "criteria", "clinical-review"],
        "appeal": ["appeal", "reconsideration", "denial"],
    }
    for intent in intents:
        for term in intent_terms.get(intent, []):
            if term in href_l or term in link_l:
                score += 1.5

    return score