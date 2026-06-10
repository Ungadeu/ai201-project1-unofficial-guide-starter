#!/usr/bin/env python3
"""
Ingest local documents and (optionally) fetch URLs; save raw text to a JSONL file.

Usage:
  python3 scripts/ingest.py planning.md README.md documents --out data/raw_documents.jsonl
  python3 scripts/ingest.py --docs documents --out data/raw_documents.jsonl --fetch

By default this will read files from the given paths or the `documents` directory.
If `--fetch` is provided, the script will also extract URLs from the text of the
input files and attempt to fetch their HTML and store a cleaned text version.
"""
import argparse
import json
import re
import sys
import time
from html import unescape
from pathlib import Path
from typing import List, Set
from urllib.parse import urlparse
from urllib.request import Request, urlopen


SUPPORTED_EXT = {".md", ".txt", ".html", ".htm"}


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
    except Exception:
        return ""


def extract_urls(text: str) -> Set[str]:
    urls = set(re.findall(r"https?://[\w\-./?&=%#,:;@+~]+", text))
    return urls


def fetch_url_text(url: str, timeout: int = 10) -> str:
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            try:
                text = raw.decode(resp.headers.get_content_charset() or "utf-8", errors="ignore")
            except Exception:
                text = raw.decode("utf-8", errors="ignore")
            # Very simple HTML-to-text: remove scripts/styles and tags
            text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
            text = re.sub(r"<[^>]+>", " ", text)
            text = unescape(text)
            text = re.sub(r"\s+", " ", text).strip()
            return text
    except Exception:
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="files or directories to ingest (default: documents)")
    ap.add_argument("--docs", default="documents", help="documents directory (default: documents)")
    ap.add_argument("--out", default="data/raw_documents.jsonl", help="output jsonl path")
    ap.add_argument("--fetch", action="store_true", help="fetch URLs found in input files")
    args = ap.parse_args()

    input_paths = [Path(p) for p in args.paths] if args.paths else [Path(args.docs)]
    files = find_files(input_paths)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    seen_urls = set()
    total = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for f in files:
            txt = read_file_text(f)
            record = {"source": str(f), "type": "file", "raw": txt}
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            total += 1
            if args.fetch:
                for url in extract_urls(txt):
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    fetched = fetch_url_text(url)
                    rec = {"source": url, "type": "url", "raw": fetched}
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    total += 1
                    time.sleep(0.1)

    print(f"Saved {total} raw documents to {out_path}")


if __name__ == "__main__":
    main()
