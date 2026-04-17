"""
build_snippets.py — CLI script for prototyping.

Reads a URL list, crawls + domain-filters pages, chunks them, assigns
bucket labels, and saves everything to a JSONL file.

Usage:
    python build_snippets.py \
        --urls  data/policies/kaiser_urls.txt \
        --out   data/policy_snippets/snippets.jsonl \
        --domain pt_rehab \
        --verbose

Each output record:
    {
      "chunk_id":    "<hash>",
      "url":         "...",
      "title":       "...",
      "section":     "...",
      "parent_url":  "...",
      "source_type": "html" | "pdf",
      "bucket":      "<label>",
      "text":        "..."
    }
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from policy_fetcher import PolicyFetcher, load_url_list
from policy_types import PolicyChunk


def save_jsonl(chunks: list[PolicyChunk], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            record = {
                "chunk_id":   chunk.chunk_id,
                "url":        chunk.url,
                "title":      chunk.title,
                "section":    chunk.section,
                "parent_url": chunk.parent_url,
                "source_type": chunk.source_type,
                "bucket":     chunk.bucket,
                "text":       chunk.text,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def print_summary(chunks: list[PolicyChunk]) -> None:
    from collections import Counter
    bucket_counts = Counter(c.bucket for c in chunks)
    url_counts = Counter(c.url for c in chunks)

    print(f"\n{'─' * 60}")
    print(f"Total chunks : {len(chunks)}")
    print(f"Unique pages : {len(url_counts)}")
    print(f"\nChunks per bucket:")
    for bucket, count in sorted(bucket_counts.items(), key=lambda x: -x[1]):
        print(f"  {bucket:<35} {count:>4}")
    print(f"{'─' * 60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build policy snippets JSONL.")
    parser.add_argument(
        "--urls",
        default="data/policies/kaiser_urls.txt",
        help="Path to URL list file (one URL per line).",
    )
    parser.add_argument(
        "--out",
        default="data/policy_snippets/snippets.jsonl",
        help="Output JSONL path.",
    )
    parser.add_argument(
        "--domain",
        default="pt_rehab",
        help="Domain filter to apply (pt_rehab | claims | pharmacy | general).",
    )
    parser.add_argument(
        "--intents",
        nargs="*",
        default=["authorization", "medical_necessity", "documentation"],
        help="Intents used for child-link scoring.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=280,
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=40,
    )
    parser.add_argument(
        "--max-children",
        type=int,
        default=6,
        help="Max child links to follow per parent page.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
    )
    args = parser.parse_args()

    print(f"[INFO] Loading URLs from: {args.urls}")
    urls = load_url_list(args.urls)
    print(f"[INFO] {len(urls)} seed URL(s) loaded. Domain filter: {args.domain}")

    fetcher = PolicyFetcher(
        chunk_size_words=args.chunk_size,
        chunk_overlap_words=args.chunk_overlap,
        max_child_links_per_page=args.max_children,
        verbose=args.verbose,
    )

    chunks = fetcher.fetch_and_chunk(
        candidate_urls=urls,
        domain=args.domain,
        intents=args.intents,
    )

    print_summary(chunks)

    output_path = Path(args.out)
    save_jsonl(chunks, output_path)
    print(f"[INFO] Saved {len(chunks)} chunks → {output_path}")


if __name__ == "__main__":
    main()