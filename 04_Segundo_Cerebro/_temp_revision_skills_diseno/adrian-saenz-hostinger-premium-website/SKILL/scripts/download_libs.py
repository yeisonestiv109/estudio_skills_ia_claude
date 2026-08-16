#!/usr/bin/env python3
"""
Library downloader — fetches GSAP, ScrollTrigger, Lenis, Three.js to project lib/.

Usage:
    python download_libs.py --target project/lib
    python download_libs.py --target project/lib --three              # also Three.js
    python download_libs.py --target project/lib --three --no-skip    # force re-download

Idempotent: if a file already exists with non-zero size, it's skipped (use --no-skip to force).

No external dependencies (uses urllib).
"""

import argparse
import os
import sys
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

USER_AGENT = "Premium-Website-Skill/1.0"

# Versioned URLs from unpkg (CDN-mirror of npm). Stable, fast, doesn't go away.
LIBS_DEFAULT = {
    "gsap.min.js":          "https://unpkg.com/gsap@3.12.5/dist/gsap.min.js",
    "ScrollTrigger.min.js": "https://unpkg.com/gsap@3.12.5/dist/ScrollTrigger.min.js",
    "lenis.min.js":         "https://unpkg.com/lenis@1.1.13/dist/lenis.min.js",
}

LIBS_THREE = {
    "three.min.js":         "https://unpkg.com/three@0.160.1/build/three.min.js",
}


def log(msg, end="\n"):
    sys.stdout.write(msg + end)
    sys.stdout.flush()


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        data = resp.read()
        dest.write_bytes(data)
        return len(data)


def main():
    parser = argparse.ArgumentParser(description="Download premium website libraries")
    parser.add_argument("--target", required=True, help="Target folder (will be created)")
    parser.add_argument("--three", action="store_true", help="Also download Three.js")
    parser.add_argument("--no-skip", action="store_true", help="Re-download even if files exist")
    args = parser.parse_args()

    target = Path(args.target)
    target.mkdir(parents=True, exist_ok=True)

    libs = dict(LIBS_DEFAULT)
    if args.three:
        libs.update(LIBS_THREE)

    log(f"\nDownloading {len(libs)} libraries to {target}\n")

    ok = 0
    skipped = 0
    fail = 0
    total_bytes = 0

    for filename, url in libs.items():
        dest = target / filename
        if dest.exists() and dest.stat().st_size > 1024 and not args.no_skip:
            log(f"  [skip]    {filename} (already present, {dest.stat().st_size // 1024} KB)")
            skipped += 1
            continue

        log(f"  [fetch]   {filename} from {url}", end="")
        try:
            size = download(url, dest)
            log(f" OK {size // 1024} KB")
            ok += 1
            total_bytes += size
        except Exception as e:
            log(f" FAIL {e}")
            fail += 1

    log("")
    log(f"Summary: {ok} downloaded, {skipped} skipped, {fail} failures.")
    log(f"Total downloaded: {total_bytes / 1024:.0f} KB")

    if fail:
        sys.exit(2)


if __name__ == "__main__":
    main()
