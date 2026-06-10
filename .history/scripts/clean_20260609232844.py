#!/usr/bin/env python3
"""
Clean raw documents produced by `scripts/ingest.py`.

Writes cleaned documents to `data/clean_documents.jsonl` with fields: source, type, raw, clean.
"""
import json
import re
from html import unescape
from pathlib import Path
from typing import List


BOILERPLATE_PHRASES = [
    "read more",
    "share",
    "share on",
    "subscribe",
    "cookie",
    "cookies",
    "accept",
    "advertis",
    "advertisement",
    "related articles",
    "comments",
    "leave a comment",
    "©",
    "all rights reserved",
    "privacy",
    "terms",
    "navigation",
    "menu",
    "skip to",
    "back to top",
    "about us",
    "contact",
    "follow",
    "tweet",
    "facebook",
    "linkedin",
    "pinterest",
    "instagram",
    "powered by",
    "powered by",
]


def remove_html(s: str) -> str:
    s = re.sub(r"(?is)<!--.*?-->", " ", s)
    s = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return s


def remove_markdown_artifacts(s: str) -> str:
    # Remove images
    s = re.sub(r"!\[.*?\]\(.*?\)", " ", s)
    # Remove blockquote markers
    s = re.sub(r"^\s*>\s?", "", s, flags=re.M)
    # Remove markdown table lines
    s = re.sub(r"(?m)^\|.*\|\s*$", "", s)
    # Remove horizontal rules
    s = re.sub(r"(?m)^[-]{3,}\s*$", "", s)
    return s


def is_boilerplate_line(line: str) -> bool:
    low = line.lower().strip()
    if not low:
        return True
    if len(low) < 4 and not any(ch.isalnum() for ch in low):
        return True
    for p in BOILERPLATE_PHRASES:
        if p in low:
            return True
    # remove table separators and markdown-only lines
    if set(low) <= set("|:- "):
        return True
    return False


def clean_text(raw: str) -> str:
    s = raw
    s = remove_html(s)
    s = remove_markdown_artifacts(s)
    s = unescape(s)
    # Normalize newlines
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # Split into lines, filter boilerplate lines
    lines = [ln.strip() for ln in s.splitlines()]
    keep: List[str] = []
    for ln in lines:
        if is_boilerplate_line(ln):
            continue
        keep.append(ln)
    # Join paragraphs: collapse multiple spaces
    text = "\n\n".join([re.sub(r"\s+", " ", p).strip() for p in "\n".join(keep).split("\n\n") if p.strip()])
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    src = Path("data/raw_documents.jsonl")
    out = Path("data/clean_documents.jsonl")
    if not src.exists():
        print("No raw documents found at data/raw_documents.jsonl. Run scripts/ingest.py first.")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with src.open("r", encoding="utf-8") as fh_in, out.open("w", encoding="utf-8") as fh_out:
        for line in fh_in:
            obj = json.loads(line)
            raw = obj.get("raw", "")
            clean = clean_text(raw)
            out_rec = {"source": obj.get("source"), "type": obj.get("type"), "raw": raw, "clean": clean}
            fh_out.write(json.dumps(out_rec, ensure_ascii=False) + "\n")
            total += 1
    print(f"Wrote {total} cleaned documents to {out}")


if __name__ == "__main__":
    main()
