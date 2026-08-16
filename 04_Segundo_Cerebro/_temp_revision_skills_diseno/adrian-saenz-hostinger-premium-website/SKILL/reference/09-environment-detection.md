# Environment Detection & Fallback Strategy

The skill should work whether or not Python is installed on the user's machine. Claude Code's Bash tool always has access to `bash` and `curl` (Git Bash on Windows, native bash on macOS/Linux), so we provide both Python and Bash flavors of every critical script.

This document explains:
- How to detect what's available.
- Which script to call in each case.
- What to do when nothing works.

---

## 1. Quick reference table

| Step | Python available | Python NOT available |
|---|---|---|
| Download libs | `python download_libs.py --target …` | `bash download_libs.sh --target …` |
| Openverse images | `python openverse_fetch.py --inline-queries ‹json› …` | `bash openverse_fetch.sh --id … --query …` (loop) |
| WebP conversion | `python webp_convert.py --src … --dst …` | **Skip.** Use originals. Modern browsers handle JPG/PNG fine. |
| Verify project | `python verify_project.py --project …` | **Use `grep` directly** for the same checks (see §6). |

---

## 2. Detect Python at the start of any session

Run this **once** before any setup commands:

```bash
PY=""
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
fi

if [ -n "$PY" ]; then
  echo "Python OK: $PY"
  $PY -c "import urllib.request" || echo "(urllib unavailable, that's odd)"
else
  echo "No Python — using Bash fallbacks"
fi
```

Save the result mentally (or in a comment). All subsequent setup branches on it.

---

## 3. Bash equivalents — what each does

### `download_libs.sh`

Equivalent to `download_libs.py`. Same arguments:
- `--target <path>` — where to put the libraries.
- `--three` — also download Three.js.
- `--no-skip` — re-download even if files exist.

Uses `curl` for downloads. Idempotent. Bash 3+ compatible (works on macOS default bash).

```bash
bash "<skill-dir>/scripts/download_libs.sh" --target project/lib
bash "<skill-dir>/scripts/download_libs.sh" --target project/lib --three
```

### `openverse_fetch.sh`

Equivalent to `openverse_fetch.py` but processes **one query at a time** (no batch JSON input). Designed to be looped.

```bash
# Single query
bash "<skill-dir>/scripts/openverse_fetch.sh" \
  --id "hero" --query "misty mountains" --aspect "wide" \
  --target project/assets/img --credits project/assets/credits.json

# Loop for multiple queries
QUERIES=(
  "hero|misty mountains forest|wide|"
  "product-1|coffee macro pour||"
  "team-maria|barista portrait|tall|"
)
for q in "${QUERIES[@]}"; do
  IFS='|' read -r id query aspect size <<< "$q"
  bash "<skill-dir>/scripts/openverse_fetch.sh" \
    --id "$id" --query "$query" --aspect "$aspect" --size "$size" \
    --target project/assets/img --credits project/assets/credits.json
  sleep 0.3   # polite throttle
done
```

The script is idempotent on `credits.json` — appends new entries without breaking existing ones.

**Limitations vs Python version:**
- No automatic retry with relaxed filters.
- JSON parsing is grep-based (works for standard Openverse responses but may fail on edge cases with embedded quotes in titles).
- Single query per call (caller loops).

For best fidelity, prefer Python when available.

---

## 4. WebP conversion when Python is missing

There's no clean Bash-only way to convert images to WebP without external tools. If Python+Pillow isn't available:

1. **Try `ffmpeg`** if it's in PATH:
   ```bash
   if command -v ffmpeg >/dev/null 2>&1; then
     ffmpeg -y -i "$INPUT" \
       -vf "scale='min(1200,iw)':-2:flags=lanczos,format=yuv420p" \
       -c:v libwebp -quality 80 -compression_level 6 \
       "$OUTPUT.webp"
   fi
   ```

2. **Try `cwebp`** (from Google's libwebp tools):
   ```bash
   if command -v cwebp >/dev/null 2>&1; then
     cwebp -q 80 "$INPUT" -o "$OUTPUT.webp"
   fi
   ```

3. **Skip conversion** — copy originals to `assets/img/` keeping their extension:
   ```bash
   cp project/assets/photos/source/* project/assets/img/
   ```
   Then in HTML, reference `.jpg`/`.png` instead of `.webp`. **This is fully acceptable.** Modern browsers (Chrome, Edge, Firefox, Safari 14+) all support JPG and PNG natively. WebP is a 30% size optimization, not a requirement.

   Update the verifier to NOT flag mixed formats if the user has legitimate JPG/PNG (which the case-3 fallback produces).

---

## 5. Verify project without `verify_project.py`

If Python isn't available, run these grep / find commands manually with the Bash tool. They're equivalent to the verifier's checks.

### Check 1 — No `<script type="module">` or imports

```bash
# Should return nothing (success) or list violations
grep -rn 'type="module"' --include="*.html" project/
grep -rn '^import\|^export' --include="*.js" project/main.js project/lib/
```

### Check 2 — All scripts have `defer`

```bash
# List all <script src=...> tags
grep -nE '<script[^>]+src=' --include="*.html" project/
# Visually check each has `defer` (skip if it has `async` or `type="module"`)
```

### Check 3 — No mixed image formats

```bash
# If you used WebP conversion: should return nothing
grep -rnE '"[^"]+\.(jpg|jpeg|png)"' --include="*.html" --include="*.css" --include="*.js" project/

# If you skipped conversion (kept originals): all references should be the original format consistently
```

### Check 4 — Referenced images exist

```bash
# Extract referenced asset paths and check existence
grep -rohE 'assets/img/[^"]+\.(webp|jpg|jpeg|png|svg)' --include="*.html" project/ | sort -u | while read path; do
  if [ ! -f "project/$path" ]; then echo "MISSING: $path"; fi
done
```

### Check 5 — One `<h1>` per page

```bash
for html in project/*.html; do
  count=$(grep -c '<h1' "$html")
  if [ "$count" -ne 1 ]; then
    echo "WARN: $html has $count <h1> tags (should be 1)"
  fi
done
```

### Check 6 — `lang` attribute on `<html>`

```bash
for html in project/*.html; do
  if ! grep -q '<html[^>]*lang=' "$html"; then
    echo "WARN: $html missing lang attribute on <html>"
  fi
done
```

### Check 7 — `alt` on every `<img>`

```bash
for html in project/*.html; do
  imgs_no_alt=$(grep -E '<img\b[^>]*>' "$html" | grep -vE 'alt=' | wc -l)
  if [ "$imgs_no_alt" -gt 0 ]; then
    echo "WARN: $html has $imgs_no_alt <img> without alt"
  fi
done
```

### Check 8 — `credits.json` is valid JSON

Without Python, validating JSON is harder. Approximate check:

```bash
# Crude — checks that braces are balanced
opens=$(tr -cd '{' < project/assets/credits.json | wc -c)
closes=$(tr -cd '}' < project/assets/credits.json | wc -c)
if [ "$opens" != "$closes" ]; then echo "ERROR: credits.json braces unbalanced"; fi

# Or just open it in Claude Code's Read tool and visually inspect
```

---

## 6. Detection helper — paste into bash session

For Claude Code to use, here's a copy-paste detection helper:

```bash
# === Premium Website Skill — environment detection ===

# Python
PY=""
if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python >/dev/null 2>&1; then PY=python
fi

# Image converter
IMG_TOOL=""
if [ -n "$PY" ] && $PY -c "from PIL import Image" 2>/dev/null; then
  IMG_TOOL="pillow"
elif command -v ffmpeg >/dev/null 2>&1; then
  IMG_TOOL="ffmpeg"
elif command -v cwebp >/dev/null 2>&1; then
  IMG_TOOL="cwebp"
fi

# Curl
CURL_OK=$(command -v curl >/dev/null 2>&1 && echo 1 || echo 0)

echo "Python:    ${PY:-(none)}"
echo "Img tool:  ${IMG_TOOL:-(none — will keep originals)}"
echo "Curl:      $([ $CURL_OK -eq 1 ] && echo OK || echo MISSING)"

if [ $CURL_OK -eq 0 ]; then
  echo "FATAL: curl is required to download libraries and stock images."
  echo "On Windows: install Git Bash. On macOS: included by default."
  exit 1
fi
```

Run this once per session. Use the variables to pick the right script flavor.

---

## 7. What if BOTH Python and curl are missing

This is the worst case. It only happens on:
- Some corporate Windows installs without Git Bash.
- Stripped-down Linux containers without networking tools.

If `curl` is missing but `wget` exists, modify the bash scripts to use `wget` instead. Otherwise:

- Tell the user (politely): "Para descargar las librerías necesito curl. En Windows con Git Bash ya viene; si no lo tienes, descarga Git for Windows desde [git-scm.com](https://git-scm.com/). Es de un solo clic y no requiere configuración."
- After they install it and confirm, re-run the setup.

This is the only environmental dependency the user might have to install. It's universal and trivial.

---

## 8. Strategy summary for Claude when invoked

```
START
 ├─ Bash tool: detect Python + curl + image tool
 ├─ If curl missing → ask user to install Git for Windows (rare)
 ├─ If Python OK → use .py scripts (preferred)
 ├─ If Python missing → use .sh scripts
 ├─ If image tool missing → use original photos (JPG/PNG)
 │   └─ Update HTML to reference original extensions
 └─ Always verify result manually with grep checks (see §5)
END
```

Never tell the user "install Python first" unless they explicitly ask. The skill should adapt and produce a working website with whatever tools are available.

---

## 9. Final note on PowerShell

This skill does NOT require PowerShell scripts because:
- macOS/Linux users don't have PowerShell.
- Windows users running Claude Code have access to Git Bash (which provides bash + curl).
- Adding PowerShell equivalents triples the script count without benefit.

If a user genuinely runs Claude Code on Windows without Git Bash, the bash scripts won't work either. They need bash. Git for Windows installs both bash and curl in one go.
