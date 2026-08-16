#!/usr/bin/env python3
"""
Openverse fetcher — downloads stock images for premium websites.

Usage:
    python openverse_fetch.py --queries queries.json --target assets/img --credits assets/credits.json
    python openverse_fetch.py --inline-queries '[{"id":"hero","query":"misty mountains","aspect":"wide"}]' --target assets/img --credits assets/credits.json

Required: Python 3.6+. No external dependencies (uses urllib).

queries.json format:
[
  { "id": "hero",       "query": "misty mountains",      "aspect": "wide", "size": "large" },
  { "id": "product-1",  "query": "espresso macro pour",  "aspect": null,    "size": "large" },
  { "id": "team-maria", "query": "barista portrait",     "aspect": "tall" }
]

Output:
- Images downloaded to <target>/<id>.<ext>
- Credits JSON written to <credits>

License filter: cc0,by,by-sa,pdm (commercially safe).
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Force UTF-8 on stdout for Windows cp1252 default
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

API_BASE = "https://api.openverse.org/v1/images/"
SAFE_LICENSES = "cc0,by,by-sa,pdm"
RENDERABLE_RE = re.compile(r"\.(jpe?g|png|webp|gif|avif)(\?|$)", re.IGNORECASE)
MAX_BYTES = 5 * 1024 * 1024  # 5 MB cap per image to avoid huge Wikimedia files
USER_AGENT = "Premium-Website-Skill/1.0 (+https://hostinger.com)"
TIMEOUT = 15

# ---- Helpers ---------------------------------------------------------------

def log(msg, end="\n"):
    sys.stdout.write(msg + end)
    sys.stdout.flush()


def http_get(url, accept="application/json"):
    """Plain GET with our user-agent. Returns (status, bytes-or-text-or-None)."""
    req = Request(url, headers={"Accept": accept, "User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read()
    except HTTPError as e:
        return e.code, None
    except (URLError, TimeoutError, Exception) as e:
        return 0, None


def search_one(query, aspect=None, size=None):
    """Search Openverse, progressively relaxing filters until we find something."""
    page_size = 6
    tries = [
        {"q": query, "license": SAFE_LICENSES, "aspect_ratio": aspect, "size": size, "mature": "false", "page_size": page_size},
        {"q": query, "license": SAFE_LICENSES, "aspect_ratio": aspect, "mature": "false", "page_size": page_size},
        {"q": query, "license": SAFE_LICENSES, "mature": "false", "page_size": page_size},
        {"q": query, "mature": "false", "page_size": page_size},
    ]
    for params in tries:
        clean = {k: v for k, v in params.items() if v not in (None, "")}
        url = API_BASE + "?" + urlencode(clean)
        status, body = http_get(url)
        if status != 200 or not body:
            continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            continue
        results = data.get("results", []) or []
        renderable = [r for r in results if r.get("url") and RENDERABLE_RE.search(r["url"])]
        if renderable:
            return renderable[0]
    return None


def download_image(url, dest_path):
    """Download to dest_path. Returns size in bytes or None on failure."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_BYTES:
                return None  # too big, skip
            data = resp.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                return None  # too big
            dest_path.write_bytes(data)
            return len(data)
    except (URLError, HTTPError, TimeoutError, Exception):
        return None


def file_ext_for(url):
    m = RENDERABLE_RE.search(url)
    return "." + m.group(1).lower() if m else ".jpg"


def clean_title(t):
    if not t:
        return "Untitled"
    t = re.sub(r"^File:", "", t)
    t = re.sub(r"\.\w+$", "", t)
    return t[:140]


# ---- Main ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fetch Openverse stock images")
    parser.add_argument("--queries", help="Path to JSON file with query list")
    parser.add_argument("--inline-queries", help="JSON string with query list (alternative to --queries)")
    parser.add_argument("--target", required=True, help="Output folder for images")
    parser.add_argument("--credits", required=True, help="Output path for credits.json")
    parser.add_argument("--throttle-ms", type=int, default=250, help="Delay between API calls (default 250ms)")
    args = parser.parse_args()

    # Load queries
    queries = []
    if args.queries:
        try:
            queries = json.loads(Path(args.queries).read_text(encoding="utf-8"))
        except Exception as e:
            log(f"ERROR reading {args.queries}: {e}")
            sys.exit(1)
    elif args.inline_queries:
        try:
            queries = json.loads(args.inline_queries)
        except Exception as e:
            log(f"ERROR parsing inline queries: {e}")
            sys.exit(1)
    else:
        log("ERROR: provide --queries or --inline-queries")
        sys.exit(1)

    if not isinstance(queries, list) or not queries:
        log("ERROR: queries must be a non-empty array")
        sys.exit(1)

    target_dir = Path(args.target)
    target_dir.mkdir(parents=True, exist_ok=True)

    credits_path = Path(args.credits)
    credits_path.parent.mkdir(parents=True, exist_ok=True)

    credits = {}
    ok = 0
    fail = 0
    total_bytes = 0

    log(f"\nFetching {len(queries)} images from Openverse...\n")

    last_call = 0.0
    for item in queries:
        item_id = item.get("id")
        query = item.get("query")
        aspect = item.get("aspect")
        size = item.get("size")

        if not item_id or not query:
            log(f"  [skip] missing id or query: {item}")
            fail += 1
            continue

        # Throttle
        elapsed = (time.time() - last_call) * 1000
        if elapsed < args.throttle_ms:
            time.sleep((args.throttle_ms - elapsed) / 1000.0)
        last_call = time.time()

        log(f"  [{item_id:18s}] \"{query}\" — searching...", end="")
        result = search_one(query, aspect=aspect, size=size)

        if not result:
            log(" FAIL no results")
            fail += 1
            continue

        url = result["url"]
        ext = file_ext_for(url)
        filename = f"{item_id}{ext}"
        dest = target_dir / filename

        size_bytes = download_image(url, dest)
        if size_bytes is None:
            log(f" FAIL download failed or too big")
            fail += 1
            continue

        total_bytes += size_bytes
        log(f" OK {size_bytes // 1024} KB - {clean_title(result.get('title', ''))[:48]}")

        # Build credits entry
        credits[item_id] = {
            "src": f"assets/img/{filename}",
            "title": clean_title(result.get("title")),
            "creator": result.get("creator") or "Unknown",
            "creator_url": result.get("creator_url"),
            "license": result.get("license") or "cc",
            "license_version": result.get("license_version") or "",
            "license_url": result.get("license_url") or "https://creativecommons.org/",
            "foreign_landing_url": result.get("foreign_landing_url") or url,
            "source": result.get("source") or result.get("provider") or "openverse",
        }
        ok += 1

    # Write credits
    credits_path.write_text(json.dumps(credits, indent=2, ensure_ascii=False), encoding="utf-8")

    log("")
    log(f"Summary: {ok} ok, {fail} failures, {total_bytes / 1024 / 1024:.1f} MB total")
    log(f"Credits manifest: {credits_path}")

    if fail and ok == 0:
        sys.exit(2)


if __name__ == "__main__":
    main()
