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


def split_paragraphs(text: str):
    pars = [p.strip() for p in text.split("\n\n") if p.strip()]
    return pars


def merge_short_paragraphs(paragraphs, min_len=200):
    if not paragraphs:
        return []
    merged = []
    buffer = ""
    for p in paragraphs:
        if not buffer:
            buffer = p
        else:
            if len(buffer) < min_len:
                buffer = buffer + "\n\n" + p
            else:
                merged.append(buffer)
                buffer = p
    if buffer:
        merged.append(buffer)
    return merged


def split_sentences(paragraph: str):
    # Simple sentence splitter: split on punctuation followed by whitespace
    sents = re.split(r'(?<=[.!?])\s+', paragraph)
    return [s.strip() for s in sents if s.strip()]


def is_heading_only(text: str) -> bool:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return True
    count_boiler = 0
    for ln in lines:
        low = ln.lower()
        if ln.startswith('#') or re.match(r'^[=\-]{2,}$', ln) or re.match(r'^\|.*\|$', ln):
            count_boiler += 1
            continue
        if len(low) < 40 and not any(c.isalnum() for c in ln):
            count_boiler += 1
            continue
        # headings or short label-like lines
        if low.endswith(':') and len(low) < 60:
            count_boiler += 1
            continue
    return (count_boiler / len(lines)) >= 0.6


def chunk_text(text: str, chunk_size: int, overlap: int):
    # Paragraph-aware merging
    paragraphs = split_paragraphs(text)
    paragraphs = merge_short_paragraphs(paragraphs, min_len=200)
    # Build a flat list of sentences preserving boundaries
    sentences = []
    for p in paragraphs:
        sents = split_sentences(p)
        if not sents:
            # fallback: split by newline
            sents = [ln.strip() for ln in p.splitlines() if ln.strip()]
        sentences.extend(sents)

    if not sentences:
        return []

    chunks = []
    i = 0
    n = len(sentences)
    idx = 0
    while i < n:
        chunk_sents = []
        length = 0
        j = i
        while j < n and length < chunk_size:
            s = sentences[j]
            chunk_sents.append(s)
            length += len(s) + 1
            j += 1
        if not chunk_sents:
            # take one sentence to make progress
            chunk_sents.append(sentences[i])
            j = i + 1
        chunk = " ".join(chunk_sents).strip()
        # Filter out heading-only chunks
        if not is_heading_only(chunk):
            start = None
            end = None
            # compute approximate char offsets by joining sentences
            # (we don't track original indices precisely)
            start = 0
            end = len(chunk)
            chunks.append((idx, start, end, chunk))
            idx += 1
        # compute overlap in sentences
        if overlap <= 0:
            next_i = j
        else:
            overlap_len = 0
            overlap_k = 0
            for snt in reversed(chunk_sents):
                overlap_len += len(snt) + 1
                overlap_k += 1
                if overlap_len >= overlap:
                    break
            next_i = max(j - overlap_k, i + 1)
        i = next_i
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
