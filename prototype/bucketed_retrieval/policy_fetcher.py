"""
policy_fetcher.py — fetch, filter, chunk.

Replaces both kp_policy_fetch.py and targeted_policy_fetcher.py.

Key changes vs previous version:
  - page_is_relevant() is called immediately after fetching each page.
    Pages that fail are dropped before any chunking happens.
  - Child link scoring uses score_child_link() from policy_domain_filter,
    which uses URL path signals FIRST (no re-fetch needed for scoring).
  - infer_bucket() lives here as the single canonical implementation.
  - PolicyChunk (from policy_types) replaces both PolicySnippet and
    RetrievedPolicyChunk.
"""

from __future__ import annotations

import hashlib
import io
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urldefrag, urlparse

import requests
import trafilatura
from bs4 import BeautifulSoup
from pypdf import PdfReader

from policy_types import PolicyPage, PolicyChunk
from policy_domain_filter import page_is_relevant, section_is_relevant, score_child_link


# ── HTTP defaults ──────────────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}
_TIMEOUT = 30
_CRAWL_DELAY = 0.25


# ── Bucket inference — single canonical implementation ────────────────────────
# Priority order matters: earlier rules win on ambiguous content.

_BUCKET_RULES: list[tuple[list[str], str]] = [
    (
        ["appeal", "grievance", "reconsideration", "denial notice"],
        "appeals",
    ),
    (
        [
            "prior authorization", "preauthorization", "utilization management",
            "clinical review criteria", "referral", "prior auth",
        ],
        "authorization",
    ),
    (
        [
            "medical necessity", "continuation of therapy",
            "discontinuation of therapy", "measurable improvement",
            "objective progress", "skilled provider", "criteria for coverage",
        ],
        "medical_necessity",
    ),
    (
        [
            "plan of care", "documentation requirement", "medical record",
            "re-evaluation", "frequency and duration", "quantitative goal",
            "physician justification", "treatment notes",
        ],
        "documentation_requirements",
    ),
    (
        [
            "coverage", "benefit", "eligibility", "excluded service",
            "evidence of coverage", "covered benefit",
        ],
        "coverage_rules",
    ),
    (
        [
            "clinical guideline", "acl", "rehabilitation protocol",
            "physical therapy guideline", "orthopedic",
        ],
        "condition_guideline",
    ),
]


def infer_bucket(*, title: str, section: str | None, url: str, text: str) -> str:
    """
    Classify a chunk into one evidence bucket.
    Uses priority-ordered rules so the most specific label wins on overlap.
    """
    blob = " ".join([
        (title or "").lower(),
        (section or "").lower(),
        (url or "").lower(),
        (text or "")[:3000].lower(),
    ])
    for keywords, bucket in _BUCKET_RULES:
        if any(kw in blob for kw in keywords):
            return bucket
    return "other"


# ── URL utilities ──────────────────────────────────────────────────────────────

def _normalize(url: str) -> str:
    url, _ = urldefrag(url)
    return url.rstrip("/")


def _is_pdf(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".pdf")


# ── Low-level fetch helpers ────────────────────────────────────────────────────

def _fetch_bytes(url: str) -> bytes:
    r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.content


def _extract_text_html(raw: bytes, url: str) -> str:
    html = raw.decode("utf-8", errors="ignore")
    extracted = trafilatura.extract(
        html,
        url=url,
        include_links=False,
        include_tables=True,
        include_formatting=True,
        favor_precision=True,
    )
    return (extracted or "").strip()


def _extract_text_pdf(raw: bytes) -> str:
    reader = PdfReader(io.BytesIO(raw))
    pages: list[str] = []
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        if t.strip():
            pages.append(t)
    return "\n\n".join(pages).strip()


def _normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _infer_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if len(line) >= 5:
            return line[:200]
    return fallback


# ── Page fetch ─────────────────────────────────────────────────────────────────

def fetch_page(url: str, parent_url: str | None = None) -> PolicyPage | None:
    """Fetch one URL and return a PolicyPage, or None on failure / empty body."""
    try:
        raw = _fetch_bytes(url)
    except Exception as exc:
        print(f"[WARN] fetch failed {url}: {type(exc).__name__}: {exc}")
        return None

    if _is_pdf(url):
        text = _extract_text_pdf(raw)
        source_type = "pdf"
    else:
        text = _extract_text_html(raw, url)
        source_type = "html"

    text = _normalize_text(text)
    if not text:
        return None

    return PolicyPage(
        url=url,
        title=_infer_title(text, fallback=url),
        text=text,
        parent_url=parent_url,
        source_type=source_type,
    )


# ── Child link discovery ───────────────────────────────────────────────────────

def discover_child_links(
    *,
    url: str,
    raw_html: bytes,
    allowed_domain: str,
    domain: str,
    intents: list[str],
    max_links: int = 6,
) -> list[str]:
    """
    Extract and score child links from a fetched HTML page.

    Uses score_child_link() from policy_domain_filter — no re-fetch needed
    because scoring is based on URL path and link anchor text only.
    """
    soup = BeautifulSoup(raw_html.decode("utf-8", errors="ignore"), "html.parser")
    candidates: list[tuple[float, str]] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue

        child_url = _normalize(urljoin(url, href))
        parsed = urlparse(child_url)

        # Only follow links on the same allowed domain
        if parsed.netloc != allowed_domain:
            continue
        if parsed.scheme not in {"http", "https"}:
            continue
        if child_url in seen:
            continue
        seen.add(child_url)

        link_text = a.get_text(" ", strip=True)
        score = score_child_link(
            link_text=link_text,
            href=child_url,
            domain=domain,
            intents=intents,
        )
        if score <= 0:
            continue

        candidates.append((score, child_url))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [url for _, url in candidates[:max_links]]


# ── Chunking / sectioning ──────────────────────────────────────────────────────

_KNOWN_HEADINGS: set[str] = {
    "principles", "process", "plan of care",
    "continuation of therapy", "discontinuation of therapy",
    "prior authorization", "coverage", "criteria", "background",
    "documentation requirements", "utilization management criteria statement",
    "why it is done", "how well it works", "risks", "appeals",
    "clinical review criteria", "member rights", "medical necessity",
}


def _looks_like_heading(line: str) -> bool:
    if not line or len(line) > 120:
        return False
    if line.endswith(":") or line.startswith("##"):
        return True
    if line.lower() in _KNOWN_HEADINGS:
        return True
    words = line.split()
    return 1 <= len(words) <= 10 and line == line.title()


def _chunk_id(url: str, heading: str, offset: int) -> str:
    return hashlib.sha256(
        f"{url}|{heading}|{offset}".encode()
    ).hexdigest()[:10]


def split_into_chunks(
    page: PolicyPage,
    *,
    domain: str,
    chunk_size_words: int = 280,
    chunk_overlap_words: int = 40,
    min_words: int = 35,
) -> list[PolicyChunk]:
    """
    Split a PolicyPage into PolicyChunks.

    Each section is first checked with section_is_relevant() before chunking.
    Chunks shorter than min_words are skipped.
    """
    lines = [l.rstrip() for l in page.text.splitlines()]
    if not lines:
        return []

    # ── segment into (heading, body_lines) pairs ──────────────────────────────
    sections: list[tuple[str, list[str]]] = []
    current_heading = "document_start"
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if _looks_like_heading(stripped):
            if current_lines:
                sections.append((current_heading, current_lines))
            current_heading = stripped[:200]
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, current_lines))

    if len(sections) <= 1:
        sections = [("document_start", lines)]

    # ── chunk each relevant section ───────────────────────────────────────────
    chunks: list[PolicyChunk] = []
    step = max(1, chunk_size_words - chunk_overlap_words)

    for heading, body_lines in sections:
        section_text = "\n".join(body_lines).strip()

        if not section_is_relevant(heading=heading, text=section_text, domain=domain):
            continue

        words = section_text.split()
        if len(words) < min_words:
            continue

        for offset in range(0, len(words), step):
            chunk_words = words[offset: offset + chunk_size_words]
            if len(chunk_words) < min_words:
                continue

            chunk_text = " ".join(chunk_words)
            cid = _chunk_id(page.url, heading, offset)

            chunks.append(
                PolicyChunk(
                    chunk_id=cid,
                    url=page.url,
                    title=page.title,
                    section=heading,
                    text=chunk_text,
                    bucket=infer_bucket(
                        title=page.title,
                        section=heading,
                        url=page.url,
                        text=chunk_text,
                    ),
                    parent_url=page.parent_url,
                    source_type=page.source_type,
                )
            )

    return chunks


# ── High-level pipeline ────────────────────────────────────────────────────────

class PolicyFetcher:
    """
    Fetch a set of candidate URLs, expand their children, filter by domain
    relevance, and return PolicyChunks ready for bucketed ranking.

    Usage:
        fetcher = PolicyFetcher(allowed_domain="wa-provider.kaiserpermanente.org")
        chunks = fetcher.fetch_and_chunk(
            candidate_urls=[...],
            domain="pt_rehab",
            intents=["authorization", "medical_necessity"],
        )
    """

    def __init__(
        self,
        *,
        allowed_domain: str = "wa-provider.kaiserpermanente.org",
        chunk_size_words: int = 280,
        chunk_overlap_words: int = 40,
        max_child_links_per_page: int = 6,
        crawl_delay: float = _CRAWL_DELAY,
        verbose: bool = False,
    ) -> None:
        self.allowed_domain = allowed_domain
        self.chunk_size_words = chunk_size_words
        self.chunk_overlap_words = chunk_overlap_words
        self.max_child_links_per_page = max_child_links_per_page
        self.crawl_delay = crawl_delay
        self.verbose = verbose

    def fetch_and_chunk(
        self,
        *,
        candidate_urls: list[str],
        domain: str,
        intents: list[str],
    ) -> list[PolicyChunk]:
        pages = self._fetch_pages(candidate_urls, domain, intents)
        chunks: list[PolicyChunk] = []
        for page in pages:
            chunks.extend(
                split_into_chunks(
                    page,
                    domain=domain,
                    chunk_size_words=self.chunk_size_words,
                    chunk_overlap_words=self.chunk_overlap_words,
                )
            )
        return chunks

    def _fetch_pages(
        self,
        candidate_urls: list[str],
        domain: str,
        intents: list[str],
    ) -> list[PolicyPage]:
        pages: list[PolicyPage] = []
        visited: set[str] = set()

        for url in candidate_urls:
            norm = _normalize(url)
            if norm in visited:
                continue
            visited.add(norm)

            page, raw = self._fetch_with_raw(norm)
            if page is None:
                continue

            # ── PAGE-LEVEL DOMAIN GATE ─────────────────────────────────────
            # This is the primary fix for unrelated docs slipping through.
            if not page_is_relevant(
                url=page.url, title=page.title, text=page.text, domain=domain
            ):
                if self.verbose:
                    print(f"[SKIP] domain filter: {norm}")
                continue

            if self.verbose:
                print(f"[KEEP] {norm}")
            pages.append(page)

            # ── Child expansion (HTML pages only) ─────────────────────────
            if raw is not None and page.source_type == "html":
                child_urls = discover_child_links(
                    url=norm,
                    raw_html=raw,
                    allowed_domain=self.allowed_domain,
                    domain=domain,
                    intents=intents,
                    max_links=self.max_child_links_per_page,
                )
                time.sleep(self.crawl_delay)

                for child_url in child_urls:
                    child_norm = _normalize(child_url)
                    if child_norm in visited:
                        continue
                    visited.add(child_norm)

                    child_page, _ = self._fetch_with_raw(child_norm, parent_url=norm)
                    if child_page is None:
                        continue

                    if not page_is_relevant(
                        url=child_page.url,
                        title=child_page.title,
                        text=child_page.text,
                        domain=domain,
                    ):
                        if self.verbose:
                            print(f"[SKIP] domain filter (child): {child_norm}")
                        continue

                    if self.verbose:
                        print(f"[KEEP] (child) {child_norm}")
                    pages.append(child_page)
                    time.sleep(self.crawl_delay)

        return pages

    def _fetch_with_raw(
        self, url: str, parent_url: str | None = None
    ) -> tuple[PolicyPage | None, bytes | None]:
        """
        Fetch a URL and return (PolicyPage, raw_bytes).
        raw_bytes is kept so we can reuse it for child-link extraction
        without a second HTTP request.
        """
        try:
            raw = _fetch_bytes(url)
        except Exception as exc:
            print(f"[WARN] fetch failed {url}: {type(exc).__name__}: {exc}")
            return None, None

        if _is_pdf(url):
            text = _extract_text_pdf(raw)
            source_type = "pdf"
            raw_for_links = None   # PDFs have no links to follow
        else:
            text = _extract_text_html(raw, url)
            source_type = "html"
            raw_for_links = raw

        text = _normalize_text(text)
        if not text:
            return None, None

        page = PolicyPage(
            url=url,
            title=_infer_title(text, fallback=url),
            text=text,
            parent_url=parent_url,
            source_type=source_type,
        )
        return page, raw_for_links


# ── CLI helper used by build_snippets.py ──────────────────────────────────────

def load_url_list(path: str | Path) -> list[str]:
    """Read a URL list file (one per line, # comments ok)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    urls: list[str] = []
    seen: set[str] = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        norm = _normalize(line)
        if norm not in seen:
            seen.add(norm)
            urls.append(norm)
    return urls