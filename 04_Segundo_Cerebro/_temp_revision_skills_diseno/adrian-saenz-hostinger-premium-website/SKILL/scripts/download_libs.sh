#!/usr/bin/env bash
# Library downloader — fetches GSAP, ScrollTrigger, Lenis, Three.js to project lib/.
#
# This is the Python-free fallback. Equivalent to scripts/download_libs.py.
# Only requires `bash` (3.x+) and `curl` (universal on macOS, Linux, Git Bash).
#
# Usage:
#   bash download_libs.sh --target project/lib
#   bash download_libs.sh --target project/lib --three           # also Three.js
#   bash download_libs.sh --target project/lib --three --no-skip # force re-download
#
# Idempotent: if a file already exists with non-zero size, skipped (use --no-skip to force).

set -e

TARGET=""
WITH_THREE=0
NO_SKIP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)   TARGET="$2"; shift 2 ;;
    --three)    WITH_THREE=1; shift ;;
    --no-skip)  NO_SKIP=1; shift ;;
    *)          echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  echo "ERROR: --target is required"
  echo "Usage: bash download_libs.sh --target project/lib [--three] [--no-skip]"
  exit 1
fi

mkdir -p "$TARGET"

# Parallel arrays — bash 3.x compatible (works on macOS default bash)
LIB_NAMES=("gsap.min.js" "ScrollTrigger.min.js" "lenis.min.js")
LIB_URLS=(
  "https://unpkg.com/gsap@3.12.5/dist/gsap.min.js"
  "https://unpkg.com/gsap@3.12.5/dist/ScrollTrigger.min.js"
  "https://unpkg.com/lenis@1.1.13/dist/lenis.min.js"
)

if [[ $WITH_THREE -eq 1 ]]; then
  LIB_NAMES+=("three.min.js")
  LIB_URLS+=("https://unpkg.com/three@0.160.1/build/three.min.js")
fi

echo ""
echo "Downloading ${#LIB_NAMES[@]} libraries to $TARGET"
echo ""

ok=0
skipped=0
failed=0
total_bytes=0

for i in "${!LIB_NAMES[@]}"; do
  name="${LIB_NAMES[$i]}"
  url="${LIB_URLS[$i]}"
  dest="$TARGET/$name"

  # Skip if already present (and >1KB to ensure not a partial download)
  if [[ $NO_SKIP -eq 0 && -s "$dest" ]]; then
    size=$(wc -c < "$dest" 2>/dev/null || echo 0)
    if [[ $size -gt 1024 ]]; then
      echo "  [skip]    $name (already present, $((size / 1024)) KB)"
      skipped=$((skipped + 1))
      continue
    fi
  fi

  printf "  [fetch]   %s ... " "$name"
  if curl -sSLf -o "$dest" -A "Premium-Website-Skill/1.0" "$url" 2>/dev/null; then
    size=$(wc -c < "$dest")
    total_bytes=$((total_bytes + size))
    echo "OK $((size / 1024)) KB"
    ok=$((ok + 1))
  else
    echo "FAIL"
    failed=$((failed + 1))
    rm -f "$dest"
  fi
done

echo ""
echo "Summary: $ok downloaded, $skipped skipped, $failed failures"
echo "Total downloaded: $((total_bytes / 1024)) KB"

if [[ $failed -gt 0 ]]; then
  exit 2
fi
