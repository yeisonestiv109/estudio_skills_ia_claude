#!/usr/bin/env python3
"""
Project verifier — runs sanity checks on a generated website BEFORE delivery.

Usage:
    python verify_project.py --project project-name

Checks:
- No <script type="module"> with relative imports.
- No import/export keywords in JS files.
- All scripts loaded with defer.
- No mixed image format references (jpg/png in HTML/CSS/JS).
- All referenced images exist.
- Splash has CSS safety net.
- IntersectionObserver thresholds reasonable.
- HTML structure: one h1, alt on imgs, lang attr.
- credits.json valid (if present).
- main.js wrapped in IIFE.
- manifest.js exposes window.__BRAND__.

Exits 0 if everything passes, 1 if warnings, 2 if errors.
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# -------- Reporting ---------------------------------------------------------

class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []

    def err(self, msg):
        self.errors.append(msg)
        print(f"  [ERROR] {msg}")

    def warn(self, msg):
        self.warnings.append(msg)
        print(f"  [WARN]  {msg}")

    def ok(self, msg):
        self.info.append(msg)
        print(f"  [OK]    {msg}")

    def section(self, title):
        print(f"\n=== {title} ===")

    def summary(self):
        print("\n" + "=" * 50)
        print(f"Summary: {len(self.info)} ok, {len(self.warnings)} warnings, {len(self.errors)} errors")
        if self.errors:
            return 2
        if self.warnings:
            return 1
        return 0


# -------- Checks ------------------------------------------------------------

def find_files(root, patterns, exclude_dirs=("node_modules", ".git", "scripts", "tools")):
    """Find files matching any of the glob patterns, excluding certain dirs."""
    results = []
    for pattern in patterns:
        for f in root.rglob(pattern):
            if not any(part in exclude_dirs for part in f.parts):
                results.append(f)
    return results


def check_no_modules(root, r):
    r.section("1. No <script type=\"module\"> imports")
    html_files = find_files(root, ["*.html"])
    bad_html = []
    for f in html_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        if 'type="module"' in text or "type='module'" in text:
            bad_html.append(f)
    if bad_html:
        for f in bad_html:
            r.err(f"{f.relative_to(root)} uses <script type=\"module\"> — forbidden, use defer instead")
    else:
        r.ok("No <script type=\"module\"> found in HTML")


def check_no_imports(root, r):
    r.section("2. No import/export in JS")
    js_files = find_files(root, ["*.js", "*.mjs"])
    js_files = [f for f in js_files if "tools" not in f.parts and "scripts" not in f.parts]

    bad = []
    for f in js_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        if re.search(r'^(import|export)\s', text, re.MULTILINE):
            bad.append(f)
    if bad:
        for f in bad:
            r.err(f"{f.relative_to(root)} uses import/export — forbidden, use IIFE pattern")
    else:
        r.ok("No import/export keywords in deliverable JS")


def check_scripts_have_defer(root, r):
    r.section("3. All <script src> have defer")
    html_files = find_files(root, ["*.html"])
    issues = []
    for f in html_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        # Find script tags with src but no defer (and no async)
        # Skip CDN-hosted scripts that are async by design (rare)
        for m in re.finditer(r'<script\s+([^>]*?)src="([^"]+)"([^>]*)>', text, re.IGNORECASE):
            attrs = (m.group(1) + " " + m.group(3)).lower()
            src = m.group(2)
            if "defer" not in attrs and "async" not in attrs and "type=\"module\"" not in attrs:
                issues.append((f.relative_to(root), src))
    if issues:
        for f, src in issues:
            r.err(f"{f}: <script src=\"{src}\"> missing defer")
    else:
        r.ok("All <script src> tags have defer")


def check_no_mixed_image_formats(root, r):
    r.section("4. No mixed .jpg / .png references")
    targets = find_files(root, ["*.html", "*.css", "*.js"])
    targets = [f for f in targets if "tools" not in f.parts and "scripts" not in f.parts and "source" not in f.parts]

    bad = []
    for f in targets:
        text = f.read_text(encoding="utf-8", errors="ignore")
        # Find .jpg/.png references in src= or url() or string literals
        for m in re.finditer(r'["\'\(]([^"\'\)]+\.(jpg|jpeg|png))["\'\)]', text, re.IGNORECASE):
            path = m.group(1)
            # Skip known okay refs
            if "favicon" in path.lower() or "credits" in path.lower():
                continue
            bad.append((f.relative_to(root), path))
    if bad:
        for f, path in bad[:10]:
            r.warn(f"{f}: references {path} — should be .webp")
        if len(bad) > 10:
            r.warn(f"...and {len(bad) - 10} more")
    else:
        r.ok("No .jpg/.png references in HTML/CSS/JS")


def check_images_exist(root, r):
    r.section("5. Referenced images exist")
    html_files = find_files(root, ["*.html"])
    missing = []
    for f in html_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'(?:src|href)="(assets/[^"]+\.(webp|jpg|jpeg|png|svg|gif|avif|ico))"', text, re.IGNORECASE):
            path = m.group(1)
            full = root / path
            if not full.exists():
                missing.append((f.relative_to(root), path))
    if missing:
        for f, path in missing:
            r.err(f"{f}: references missing file {path}")
    else:
        r.ok("All referenced images exist")


def check_splash_safety(root, r):
    r.section("6. Splash safety net")
    css_files = find_files(root, ["*.css"])
    has_splash_in_css = False
    has_safety = False
    for f in css_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        if ".splash" in text:
            has_splash_in_css = True
            if "splashSafety" in text or ("animation:" in text and "4." in text and "splash" in text.lower()):
                has_safety = True
                break
    if has_splash_in_css:
        if has_safety:
            r.ok("Splash has CSS safety animation")
        else:
            r.warn("Splash CSS exists but no safety animation found (4.5s timeout)")
    else:
        r.ok("No splash defined (skipping check)")


def check_intersection_observer_thresholds(root, r):
    r.section("7. IntersectionObserver thresholds reasonable")
    js_files = find_files(root, ["*.js"])
    js_files = [f for f in js_files if "tools" not in f.parts and "scripts" not in f.parts]
    high_thresholds = []
    for f in js_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'threshold:\s*([0-9.]+)', text):
            val = float(m.group(1))
            if val > 0.18:
                high_thresholds.append((f.relative_to(root), val))
    if high_thresholds:
        for f, v in high_thresholds:
            r.warn(f"{f}: IntersectionObserver threshold {v} too high (use ≤0.05 + safety setTimeout)")
    else:
        r.ok("IntersectionObserver thresholds reasonable")


def check_html_structure(root, r):
    r.section("8. HTML structure")
    html_files = find_files(root, ["*.html"])
    for f in html_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        # exactly one h1
        h1_count = len(re.findall(r'<h1\b', text, re.IGNORECASE))
        if h1_count == 0:
            r.warn(f"{f.relative_to(root)}: no <h1> found")
        elif h1_count > 1:
            r.warn(f"{f.relative_to(root)}: {h1_count} <h1> tags (should be exactly 1)")
        # lang attr
        if not re.search(r'<html[^>]*\blang=', text, re.IGNORECASE):
            r.warn(f"{f.relative_to(root)}: <html> missing lang attribute")
        # imgs without alt
        imgs_without_alt = []
        for m in re.finditer(r'<img\s+([^>]+)>', text, re.IGNORECASE):
            attrs = m.group(1)
            if "alt=" not in attrs:
                imgs_without_alt.append(m.group(0)[:80])
        if imgs_without_alt:
            r.warn(f"{f.relative_to(root)}: {len(imgs_without_alt)} <img> without alt")


def check_credits_json(root, r):
    r.section("9. credits.json (if present)")
    credits_path = root / "assets" / "credits.json"
    if not credits_path.exists():
        r.ok("No credits.json (skipping)")
        return
    try:
        data = json.loads(credits_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        r.err(f"credits.json is invalid JSON: {e}")
        return
    if not isinstance(data, dict):
        r.err("credits.json must be a dict {id: entry}")
        return
    required_fields = {"src", "title", "creator", "license", "license_url", "foreign_landing_url"}
    bad = []
    for key, entry in data.items():
        if not isinstance(entry, dict):
            bad.append((key, "not an object"))
            continue
        missing = required_fields - set(entry.keys())
        if missing:
            bad.append((key, f"missing fields: {', '.join(missing)}"))
    if bad:
        for k, why in bad:
            r.err(f"credits.json[{k}]: {why}")
    else:
        r.ok(f"credits.json has {len(data)} valid entries")


def check_main_js_iife(root, r):
    r.section("10. main.js / lib/manifest.js patterns")
    main_js = root / "main.js"
    if main_js.exists():
        text = main_js.read_text(encoding="utf-8", errors="ignore")
        # Should start with IIFE
        if not re.match(r'\s*\(function\s*\(\)\s*\{|\s*!function\s*\(\)\s*\{|\s*\(\(\)\s*=>\s*\{', text):
            r.warn("main.js doesn't start with IIFE — content may leak globals")
        else:
            r.ok("main.js wrapped in IIFE")
    manifest_js = root / "lib" / "manifest.js"
    if manifest_js.exists():
        text = manifest_js.read_text(encoding="utf-8", errors="ignore")
        if "window.__BRAND__" not in text:
            r.warn("lib/manifest.js doesn't define window.__BRAND__ — main.js may not find data")
        else:
            r.ok("manifest.js exposes window.__BRAND__")


def check_libs_present(root, r):
    r.section("11. Libraries present in lib/")
    lib_dir = root / "lib"
    if not lib_dir.exists():
        r.warn("lib/ folder missing — run download_libs.py first")
        return
    expected = ["gsap.min.js", "ScrollTrigger.min.js", "lenis.min.js"]
    missing = [name for name in expected if not (lib_dir / name).exists()]
    if missing:
        r.warn(f"lib/ missing: {', '.join(missing)}")
    else:
        r.ok("All required libs present in lib/")


# -------- Main --------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Verify a generated website project")
    parser.add_argument("--project", required=True, help="Path to the project folder")
    args = parser.parse_args()

    root = Path(args.project).resolve()
    if not root.exists():
        print(f"ERROR: project folder doesn't exist: {root}")
        sys.exit(2)
    if not (root / "index.html").exists():
        print(f"ERROR: no index.html in {root}")
        sys.exit(2)

    print(f"\nVerifying project: {root}")

    r = Report()
    check_no_modules(root, r)
    check_no_imports(root, r)
    check_scripts_have_defer(root, r)
    check_no_mixed_image_formats(root, r)
    check_images_exist(root, r)
    check_splash_safety(root, r)
    check_intersection_observer_thresholds(root, r)
    check_html_structure(root, r)
    check_credits_json(root, r)
    check_main_js_iife(root, r)
    check_libs_present(root, r)

    sys.exit(r.summary())


if __name__ == "__main__":
    main()
