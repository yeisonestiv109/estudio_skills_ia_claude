#!/usr/bin/env python3
"""
WebP converter — converts user-supplied photos to optimized WebP.

Usage:
    python webp_convert.py --src assets/photos/source --dst assets/img

Auto-installs Pillow if missing (silent, --user). Falls back gracefully if it can't.

File-name heuristics:
    hero*.{jpg,png,heic}     → hero treatment (max 2000px, q78)
    logo*.{png,svg}          → alpha-preserved (max 600px, q80)
    *-thumb*                 → thumbnail (max 560px, q75)
    avatar*, portrait*, team*→ portrait (max 600px, q78)
    All other                → standard (max 1200px, q80)

Output:
    Each input → one or more WebP in dst.
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def log(msg, end="\n"):
    sys.stdout.write(msg + end)
    sys.stdout.flush()


def ensure_pillow():
    """Try to import Pillow, install silently if missing."""
    try:
        from PIL import Image
        return Image
    except ImportError:
        log("Pillow not found, installing silently...")
        for flags in (["--user", "--quiet"], ["--quiet"], []):
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", *flags, "pillow"],
                    check=True, capture_output=True, timeout=120
                )
                from PIL import Image
                log("Pillow installed.")
                return Image
            except Exception:
                continue
        log("WARNING: could not install Pillow. Falling back to copy-only mode.")
        return None


def try_install_heif():
    """Best-effort: install pillow-heif for .heic support."""
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
        return True
    except ImportError:
        for flags in (["--user", "--quiet"], ["--quiet"]):
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", *flags, "pillow-heif"],
                    check=True, capture_output=True, timeout=120
                )
                from pillow_heif import register_heif_opener
                register_heif_opener()
                return True
            except Exception:
                continue
        return False


# -------- Categorization heuristic ------------------------------------------

def categorize(filename):
    """Return (max_width, quality, preserve_alpha, label)."""
    name = filename.lower()
    if name.startswith("hero"):
        return (2000, 78, False, "hero")
    if name.startswith("logo"):
        return (600, 80, True, "logo")
    if "thumb" in name:
        return (560, 75, False, "thumb")
    if any(name.startswith(prefix) for prefix in ("avatar", "portrait", "team", "person")):
        return (600, 78, False, "portrait")
    return (1200, 80, False, "standard")


def output_filename(src_filename):
    """Strip original extension, return .webp."""
    p = Path(src_filename)
    return p.stem + ".webp"


def has_alpha(img):
    return img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)


# -------- Conversion --------------------------------------------------------

def convert_one(Image, src_path, dst_path, max_width, quality, preserve_alpha):
    """Open, resize, convert to WebP. Returns size in bytes or None on failure."""
    try:
        with Image.open(src_path) as img:
            # Convert mode if needed
            if preserve_alpha and has_alpha(img):
                img = img.convert("RGBA")
            else:
                if img.mode in ("RGBA", "LA", "P"):
                    # Composite onto white if no alpha needed
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    bg.paste(img, mask=img.split()[-1] if has_alpha(img) else None)
                    img = bg
                elif img.mode != "RGB":
                    img = img.convert("RGB")

            # Resize if wider than max
            if img.width > max_width:
                ratio = max_width / img.width
                new_size = (max_width, int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)

            # Save as WebP
            img.save(dst_path, "WEBP", quality=quality, method=6)
            return dst_path.stat().st_size
    except Exception as e:
        log(f"    ERROR converting {src_path.name}: {e}")
        return None


def fallback_copy(src_path, dst_path):
    """If Pillow unavailable, just copy the file with original extension."""
    try:
        # Remove .webp extension we expected, keep original
        new_dst = dst_path.with_suffix(src_path.suffix.lower())
        shutil.copy2(src_path, new_dst)
        return new_dst.stat().st_size
    except Exception:
        return None


# -------- Main --------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".heic", ".heif", ".avif"}


def main():
    parser = argparse.ArgumentParser(description="Convert user photos to optimized WebP")
    parser.add_argument("--src", required=True, help="Source folder with original images")
    parser.add_argument("--dst", required=True, help="Destination folder for WebP output")
    parser.add_argument("--max-width", type=int, default=None, help="Override max width for all images")
    parser.add_argument("--quality", type=int, default=None, help="Override quality for all images")
    args = parser.parse_args()

    src_dir = Path(args.src)
    dst_dir = Path(args.dst)

    if not src_dir.exists():
        log(f"Source folder doesn't exist (yet): {src_dir}")
        log("This is OK if the user hasn't uploaded photos. Skipping conversion.")
        sys.exit(0)

    dst_dir.mkdir(parents=True, exist_ok=True)

    # Find all source images
    source_files = sorted([
        f for f in src_dir.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ])

    if not source_files:
        log(f"No images found in {src_dir}. Nothing to convert.")
        sys.exit(0)

    log(f"\nConverting {len(source_files)} images from {src_dir} → {dst_dir}\n")

    # Setup Pillow + HEIC
    Image = ensure_pillow()
    heic_files = [f for f in source_files if f.suffix.lower() in (".heic", ".heif")]
    if heic_files:
        if not try_install_heif():
            log(f"WARNING: {len(heic_files)} .heic files will be skipped (could not install pillow-heif).")

    ok = 0
    fail = 0
    skipped = 0
    total_bytes = 0

    for src_file in source_files:
        # Skip HEIC if no HEIF support
        if src_file.suffix.lower() in (".heic", ".heif") and Image is not None:
            try:
                from pillow_heif import register_heif_opener
            except ImportError:
                log(f"  [skip-heic] {src_file.name}")
                skipped += 1
                continue

        max_w, q, alpha, label = categorize(src_file.name)
        if args.max_width: max_w = args.max_width
        if args.quality: q = args.quality

        out_filename = output_filename(src_file.name)
        dst_path = dst_dir / out_filename

        log(f"  [{label:9s}] {src_file.name} → {out_filename}", end="")

        if Image is None:
            # Fallback: copy without conversion
            size = fallback_copy(src_file, dst_path)
            if size:
                log(f" (copied, {size//1024} KB)")
                ok += 1
                total_bytes += size
            else:
                log(" FAIL")
                fail += 1
        else:
            size = convert_one(Image, src_file, dst_path, max_w, q, alpha)
            if size is not None:
                log(f" OK {size // 1024} KB ({max_w}px q{q})")
                ok += 1
                total_bytes += size
            else:
                log(" FAIL FAILED")
                fail += 1

    log("")
    log(f"Summary: {ok} ok, {fail} failures, {skipped} skipped. {total_bytes / 1024 / 1024:.1f} MB total.")

    if fail and ok == 0:
        sys.exit(2)


if __name__ == "__main__":
    main()
