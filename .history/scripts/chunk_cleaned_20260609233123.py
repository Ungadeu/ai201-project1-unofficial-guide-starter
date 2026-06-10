#!/usr/bin/env python3
"""
Chunk cleaned documents (data/clean_documents.jsonl) using settings from planning.md.

Outputs `data/chunks.jsonl` with one JSON record per chunk.
"""
import json
import re
import argparse
import os
from pathlib import Path
from typing import List, Dict


def read_planning_chunk_settings(planning_path: Path) -> Dict[str, int]:
    if not planning_path.exists():
        return {}
    text = planning_path.read_text(encoding="utf-8")
    m = re.search(r"\*\*Chunk size:\*\*\s*([0-9,]+)\s*characters", text, re.IGNORECASE)
    overlap_m = re.search(r"\*\*Overlap:\*\s*([0-9,]+)\s*characters", text, re.IGNORECASE)
    result = {}
    if m:
        result["chunk_size"] = int(m.group(1).replace(",", ""))
    if overlap_m:
        result["overlap"] = int(overlap_m.group(1).replace(",", ""))
    return result


def chunk_text(text: str, chunk_size: int, overlap: int):
    if not text:
        return []
    step = max(1, chunk_size - overlap)
    chunks = []
    start = 0
    L = len(text)
    idx = 0
    while start < L:
        end = min(start + chunk_size, L)
        chunk = text[start:end]
        chunks.append((idx, start, end, chunk))
        idx += 1
        if end == L:
            break
        start += step
    return chunks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", default="data/clean_documents.jsonl")
    ap.add_argument("--out", default="data/chunks.jsonl")
    ap.add_argument("--planning", default="planning.md")
    ap.add_argument("--chunk-size", type=int, help="override chunk size in characters")
    ap.add_argument("--overlap", type=int, help="override overlap in characters")
    args = ap.parse_args()

    planning = Path(args.planning)
    settings = read_planning_chunk_settings(planning)
    chunk_size = args.chunk_size or settings.get("chunk_size") or 800
    overlap = args.overlap or settings.get("overlap") or 150

    clean_path = Path(args.clean)
    if not clean_path.exists():
        print("Clean documents file not found. Run scripts/clean.py first.")
        return

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total_chunks = 0
    with clean_path.open("r", encoding="utf-8") as fh_in, out_path.open("w", encoding="utf-8") as fh_out:
        for doc_idx, line in enumerate(fh_in):
            obj = json.loads(line)
            source = obj.get("source")
            text = obj.get("clean") or obj.get("raw") or ""
            chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
            for idx, start, end, chunk in chunks:
                rec = {
                    "source": os.path.relpath(str(source), start=str(Path.cwd())),
                    "doc_index": doc_idx,
                    "chunk_index": idx,
                    "start": start,
                    "end": end,
                    "text": chunk,
                    "chunk_size": chunk_size,
                    "overlap": overlap,
                }
                fh_out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            total_chunks += len(chunks)

    print(f"Wrote {total_chunks} chunks to {out_path} (chunk_size={chunk_size}, overlap={overlap})")


if __name__ == "__main__":
    main()
