#!/usr/bin/env python3
"""
Simple document loader + cleaner + chunker.

Usage examples:
  python scripts/chunker.py --docs documents --out data/chunks.jsonl
  python scripts/chunker.py planning.md README.md --out data/chunks.jsonl

By default the script will try to read chunk size and overlap from `planning.md`.
If not found, defaults to 800 char chunks and 150 char overlap.
"""
import argparse
import json
import os
import re
from html import unescape
from pathlib import Path
from typing import List, Dict


def read_planning_chunk_settings(planning_path: Path) -> Dict[str, int]:
    if not planning_path.exists():
        return {}
    text = planning_path.read_text(encoding="utf-8")
    # Try to find patterns like '800 characters' after the Chunk size header
    m = re.search(r"\*\*Chunk size:\*\*\s*([0-9,]+)\s*characters", text, re.IGNORECASE)
    overlap_m = re.search(r"\*\*Overlap:\*\s*([0-9,]+)\s*characters", text, re.IGNORECASE)
    result = {}
    if m:
        result["chunk_size"] = int(m.group(1).replace(",", ""))
    if overlap_m:
        result["overlap"] = int(overlap_m.group(1).replace(",", ""))
    return result


def clean_text(s: str) -> str:
    # Remove YAML frontmatter
    s = re.sub(r"^---[\s\S]*?---\s*", "", s)
    # Strip HTML tags
    s = re.sub(r"<[^>]+>", " ", s)
    # Convert HTML entities
    s = unescape(s)
    # Normalize whitespace
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse multiple newlines to two, preserve paragraph breaks
    s = re.sub(r"\n{3,}", "\n\n", s)
    # Replace newlines with spaces to avoid breaking context within chunks
    s = re.sub(r"\n", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[Dict]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    step = max(1, chunk_size - overlap)
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end]
        chunks.append({"start": start, "end": end, "text": chunk})
        if end == text_len:
            break
        start += step
    return chunks


def load_files(paths: List[Path]) -> Dict[Path, str]:
    loaded = {}
    for p in paths:
        if p.is_dir():
            for child in sorted(p.iterdir()):
                if child.is_file() and child.suffix.lower() in (".txt", ".md", ".html"):
                    loaded[child] = child.read_text(encoding="utf-8", errors="ignore")
        elif p.is_file():
            loaded[p] = p.read_text(encoding="utf-8", errors="ignore")
    return loaded


def gather_input_paths(args) -> List[Path]:
    if args.paths:
        return [Path(p) for p in args.paths]
    return [Path(args.docs)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="files or directories to ingest (default: documents)")
    ap.add_argument("--docs", default="documents", help="documents directory (default: documents)")
    ap.add_argument("--out", default="data/chunks.jsonl", help="output jsonl path")
    ap.add_argument("--planning", default="planning.md", help="planning.md path to read chunk settings from")
    ap.add_argument("--chunk-size", type=int, help="override chunk size in characters")
    ap.add_argument("--overlap", type=int, help="override overlap in characters")
    args = ap.parse_args()

    planning = Path(args.planning)
    settings = read_planning_chunk_settings(planning)
    chunk_size = args.chunk_size or settings.get("chunk_size") or 800
    overlap = args.overlap or settings.get("overlap") or 150

    input_paths = gather_input_paths(args)
    files = load_files(input_paths)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total_chunks = 0
    if not files:
        print("No input files found. Please add files to the 'documents' folder or pass paths.")

    with out_path.open("w", encoding="utf-8") as fh:
        for path, raw in files.items():
            cleaned = clean_text(raw)
            chunks = chunk_text(cleaned, chunk_size=chunk_size, overlap=overlap)
            for c in chunks:
                record = {
                    "source": os.path.relpath(str(path), start=str(Path.cwd())),
                    "start": c["start"],
                    "end": c["end"],
                    "text": c["text"],
                    "chunk_size": chunk_size,
                    "overlap": overlap,
                }
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            total_chunks += len(chunks)

    print(f"Wrote {total_chunks} chunks to {out_path}")


if __name__ == "__main__":
    main()
