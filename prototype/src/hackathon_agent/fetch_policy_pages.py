### Fetch policy pages 
# read url, fetch each url once, save cleaned text locally into a cache folder 

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

import requests
import trafilatura
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
# TODO: current hard coded url location
# need revision on this part 
url_file = "/home/smooi/RecoveryIntelligenceSystem/data/policies/kaiser_urls.txt"
cache_dir = "/home/smooi/RecoveryIntelligenceSystem/data/policy_cache"


def slugify(text: str, max_length: int = 80) -> str:
    text = text.strip().lower()
    text = re.sub(r"https?://", "", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:max_length] or "document"


def short_hash(text: str, length: int = 10) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def read_url_file(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"URL file not found: {path}")

    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)

    if not urls:
        raise ValueError(f"No URLs found in {path}")

    return urls


def fetch_bytes(url: str, timeout: int = 30) -> bytes:
    response = requests.get(
        url,
        timeout=timeout,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        },
    )
    response.raise_for_status()
    return response.content


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    import io

    reader = PdfReader(io.BytesIO(pdf_bytes))
    texts: list[str] = []

    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            texts.append(page_text)

    return "\n\n".join(texts).strip()


def extract_text_from_html_bytes(html_bytes: bytes, url: str) -> str:
    html_str = html_bytes.decode("utf-8", errors="ignore")
    extracted = trafilatura.extract(
        html_str,
        url=url,
        include_links=False,
        include_tables=True,
        include_formatting=True,
        favor_precision=True,
    )
    return (extracted or "").strip()


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def infer_title_from_text(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if len(line) >= 5:
            return line[:200]
    return fallback


def save_cache_file(
    *,
    cache_dir: Path,
    url: str,
    title: str,
    content: str,
) -> Path:
    slug = slugify(title) or slugify(url)
    suffix = short_hash(url)
    output_path = cache_dir / f"{slug}_{suffix}.txt"

    serialized = (
        f"URL: {url}\n"
        f"TITLE: {title}\n"
        f"CONTENT:\n"
        f"{content}\n"
    )
    output_path.write_text(serialized, encoding="utf-8")
    return output_path


def fetch_and_cache_url(url: str, cache_dir: Path) -> Path | None:
    raw = fetch_bytes(url)

    if url.lower().endswith(".pdf"):
        text = extract_text_from_pdf_bytes(raw)
    else:
        text = extract_text_from_html_bytes(raw, url)

    text = normalize_text(text)
    if not text:
        print(f"[WARN] No extractable text for: {url}")
        return None

    title = infer_title_from_text(text, fallback=url)
    output_path = save_cache_file(
        cache_dir=cache_dir,
        url=url,
        title=title,
        content=text,
    )
    print(f"[OK] Cached: {url} -> {output_path.name}")
    return output_path


def main(
    url_file =  Path(url_file),
    cache_dir = Path(cache_dir),
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    urls = read_url_file(url_file)

    print(f"Reading URLs from: {url_file}")
    print(f"Caching extracted text to: {cache_dir}")
    print(f"Found {len(urls)} URL(s)\n")

    for url in urls:
        try:
            fetch_and_cache_url(url, cache_dir)
        except Exception as exc:
            print(f"[ERROR] Failed for {url}\n  {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()