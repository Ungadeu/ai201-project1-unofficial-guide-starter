#!/usr/bin/env python3
"""
Import plain text source files into data/raw_documents.jsonl and optionally clean them.

Usage:
  python scripts/import_raw_texts.py documents --out data/raw_documents.jsonl
  python scripts/import_raw_texts.py documents --out data/raw_documents.jsonl --clean

If the input path is a directory, this script will recursively import all .txt, .md, .html, and .htm files.
"""
import argparse
import json
from pathlib import Path
from typing import List

SUPPORTED_EXT = {".txt", ".md", ".html", ".htm"}


def find_files(paths: List[Path]) -> List[Path]:
    files = []
    for p in paths:
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file() and child.suffix.lower() in SUPPORTED_EXT:
                    files.append(child)
        elif p.is_file():
            files.append(p)
    return files


def read_file_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        print(f"Warning: could not read {p}: {exc}")
        return ""


def clean_text(raw: str) -> str:
    # Minimal clean pass matching scripts/clean.py behavior.
    from html import unescape
    import re

    def remove_html(s: str) -> str:
        s = re.sub(r"(?is)<!--.*?-->", " ", s)
        s = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", s)
        s = re.sub(r"<[^>]+>", " ", s)
        return s

    def remove_markdown_artifacts(s: str) -> str:
        s = re.sub(r"!\[.*?\]\(.*?\)", " ", s)
        s = re.sub(r"^\s*>\s?", "", s, flags=re.M)
        s = re.sub(r"(?m)^\|.*\|\s*$", "", s)
        s = re.sub(r"(?m)^[-]{3,}\s*$", "", s)
        return s

    def is_boilerplate_line(line: str) -> bool:
        low = line.lower().strip()
        if not low:
            return True
        if len(low) < 4 and not any(ch.isalnum() for ch in low):
            return True
        boilerplate_phrases = [
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
        ]
        for p in boilerplate_phrases:
            if p in low:
                return True
        if set(low) <= set("|:- "):
            return True
        return False

    text = raw
    text = remove_html(text)
    text = remove_markdown_artifacts(text)
    text = unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.strip() for ln in text.splitlines()]
    keep = [ln for ln in lines if not is_boilerplate_line(ln)]
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in "\n".join(keep).split("\n\n") if p.strip()]
    result = re.sub(r"\s+", " ", "\n\n".join(paragraphs)).strip()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Import raw source text files into data/raw_documents.jsonl")
    parser.add_argument("paths", nargs="*", default=["documents"], help="Files or directories to import")
    parser.add_argument("--out", default="data/raw_documents.jsonl", help="Path to output raw_documents.jsonl")
    parser.add_argument("--clean", action="store_true", help="Also write cleaned documents to data/clean_documents.jsonl")
    args = parser.parse_args()

    input_paths = [Path(p) for p in args.paths]
    files = find_files(input_paths)
    if not files:
        print("No supported source files found. Place your raw source text files in 'documents/' or pass file paths.")
        return

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    raw_records = []
    for src in files:
        raw_text = read_file_text(src)
        if raw_text.strip():
            raw_records.append({
                "source": str(src),
                "type": "file",
                "raw": raw_text,
            })

    if not raw_records:
        print("No readable raw text could be imported from the provided paths.")
        return

    with out_path.open("w", encoding="utf-8") as fh:
        for rec in raw_records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Wrote {len(raw_records)} raw documents to {out_path}")

    if args.clean:
        clean_path = Path("data/clean_documents.jsonl")
        with clean_path.open("w", encoding="utf-8") as fh_clean:
            for rec in raw_records:
                clean_text_value = clean_text(rec["raw"])
                out_rec = {
                    "source": rec["source"],
                    "type": rec["type"],
                    "raw": rec["raw"],
                    "clean": clean_text_value,
                }
                fh_clean.write(json.dumps(out_rec, ensure_ascii=False) + "\n")
        print(f"Wrote {len(raw_records)} cleaned documents to {clean_path}")


if __name__ == "__main__":
    main()
