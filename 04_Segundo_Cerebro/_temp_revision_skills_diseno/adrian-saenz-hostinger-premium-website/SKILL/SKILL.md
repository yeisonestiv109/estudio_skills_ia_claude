---
name: adrian-saenz-hostinger-premium-website
description: Generate visually stunning, robust static websites (HTML/CSS/vanilla JS) ready to drag-and-drop to Hostinger or any static host. Premium editorial design with 2026-grade animations, 3D effects, scroll-driven storytelling, parallax, custom cursors. No build step, no npm. Use this skill when the user wants to create ANY website (landing, portfolio, restaurant, agency, newsletter, e-commerce, blog, SaaS) with a "wow factor" visual quality. Triggered by phrases like "create a website", "build me a landing", "I need a web for my [business]", "design a site for", "haz una web", "crea una landing", "necesito una web".
---

# Premium Static Website Generator — Skill

Generate **drag-and-drop websites** for Hostinger / any static host with the visual quality of award-winning studios (Active Theory, Locomotive, Resn, &Walsh) but **zero build step, zero npm, zero frameworks**. Pure HTML + CSS + vanilla JS + local libraries (GSAP, Lenis, Three.js when needed).

## When to use this skill

Trigger this skill when the user asks for:
- A **new website** of any kind (landing page, portfolio, restaurant, agency, newsletter, blog, SaaS, e-commerce, event, hotel, gallery, etc.).
- A "premium" / "wow" / "increíble" web — explicitly visual ambition.
- Spanish or English user; the skill handles both.
- The user is **non-technical**: they will not run npm, install dependencies, configure servers. They want a folder they can upload by FTP.

Do **not** use this skill for:
- Editing an existing complex codebase (use direct tools).
- A web app with backend / database (this skill is for static brochure-style sites).
- Documentation-only / no design ambition (use plain HTML).

---

## ⚠️ Read-this-first instructions for Claude

Before writing a single line, **read these reference files in order**. They contain critical rules learned from real projects:

1. `reference/09-environment-detection.md` — **mandatory.** Detect what tools the user has (Python, curl, image converters). The skill works with or without Python. Run the detection helper at the start of every session.
2. `reference/04-critical-gotchas.md` — **mandatory.** Errors that break the website silently if ignored. Special attention to A.13/A.14 (cache + ES modules) and B.1.4 (Lenis fragility).
3. `reference/10-deployment-and-cache.md` — **mandatory.** The single biggest source of post-launch confusion is cache. Apply the 3-layer strategy on every deploy.
4. `reference/07-windows-troubleshooting.md` — **mandatory.** Windows ships `prefers-reduced-motion: reduce` ON by default in many setups. If we gate effects with it, the user opens the site on their PC and sees a flat website. This is the #1 source of "the site looks dead" complaints.
5. `reference/02-archetypes.md` — pick ONE archetype before generating. **Never combine two archetypes**; they produce confused webs.
6. `reference/06-diversity-guardrails.md` — **mandatory.** This skill is fed with three reference projects (Nómada, 911 Restaurante, The Gambit). The temptation is to copy them. **Don't.** Use the archetype rotation rules to ensure every output is meaningfully different.

Then, depending on what the user needs:

7. `reference/01-stack-and-conventions.md` — file structure, script load order, IIFE pattern.
8. `reference/03-effects-catalog.md` — copy/paste-ready effect snippets.
9. `reference/05-image-and-asset-pipeline.md` — when to fetch from Openverse, when to ask the user for photos, how to convert to WebP automatically.
10. `reference/08-pre-deploy-checklist.md` — run before declaring done.

---

## Conversation flow (be efficient — minimize user friction)

The user is non-technical. Default behavior: **decide silently** unless absolutely necessary. The user should answer 4–6 short questions max, total.

### Step 1 — User dump

The user will describe their project in their own words. Capture:
- **Type of business / project** (restaurant, agency, portfolio, etc.).
- **Brand name** (if mentioned).
- **Tone** (luxury / playful / serious / etc.) inferred or stated.
- **Photos**: do they have their own?  
- **Special features** mentioned (booking form, menu, gallery, blog…).

**Don't ask follow-ups yet.** Read what they wrote, then ask the minimum.

### Step 2 — Minimum follow-up questions

Ask **only what cannot be reasonably inferred**. Use ONE message with all questions in a numbered list. Maximum 5 questions. Keep each ≤15 words.

Required:
1. **Brand name** (if not given).
2. **Photos**: ask the user to either **drop their own images in `assets/photos/source/`** OR confirm they want stock images from Openverse. Default = Openverse if no answer.
3. **CTA goal** (book table / subscribe / contact / buy / learn more).
4. **Anything specific the website MUST include** (free text, optional).
5. **Number of pages** (one-page is default; multi-page if they need menu/blog/portfolio detail).

Do **not** ask about:
- Color palette → choose based on archetype + industry.
- Fonts → choose based on archetype.
- Layout → pick from archetype.
- Effects → pick 4–5 from archetype's signature set.
- Tech decisions of any kind.

### Step 3 — Silent archetype selection

Map the brief to ONE archetype from `reference/02-archetypes.md`:

| Industry hint | Archetype default |
|---|---|
| Restaurant / hotel / hospitality | **Editorial Dark Warm** or **Light Editorial Cream** |
| Travel agency / experiences | **Light Editorial Cream** or **Magazine Multi-page** |
| Newsletter / publication | **Cinematic 3D Storytelling** or **Brutalist Grid** |
| Tech / SaaS / startup | **Mouse-Reactive Gradient** or **Glassmorphism Modern** |
| Portfolio / studio / creative | **3D Cinematic** or **Brutalist Grid** or **Liquid Wave** |
| Boutique product / luxury | **Glassmorphism Modern** or **Editorial Dark Warm** |
| Café / artisan / lifestyle | **Light Editorial Cream** or **Magazine Multi-page** |
| Cultural / gallery / event | **Brutalist Grid** or **Newspaper Editorial** |

If two archetypes fit equally → **rotate**: pick the one you've used least recently (see `reference/06-diversity-guardrails.md` for the rotation log mechanic).

### Step 4 — Silent setup

Run setup scripts WITHOUT asking the user. Use the Bash tool. **Detect Python availability first** and pick the right script flavor (see `reference/09-environment-detection.md` for the full strategy):

```bash
# Detect Python — sets PY to python3, python, or empty
PY=""
if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python >/dev/null 2>&1; then PY=python
fi

# 1. Create project folder
mkdir -p {project-name}/assets/img
mkdir -p {project-name}/assets/photos/source
mkdir -p {project-name}/lib
mkdir -p {project-name}/tools

# 2. Download libraries — Python preferred, Bash fallback
if [ -n "$PY" ]; then
  $PY "<skill-dir>/scripts/download_libs.py" --target {project-name}/lib
else
  bash "<skill-dir>/scripts/download_libs.sh" --target {project-name}/lib
fi

# 3. Stock images from Openverse — same pattern
if [ -n "$PY" ]; then
  $PY "<skill-dir>/scripts/openverse_fetch.py" --inline-queries '...' --target {...}/assets/img --credits {...}/assets/credits.json
else
  # Bash version: one query per call (loop in shell)
  for q in $QUERIES; do
    bash "<skill-dir>/scripts/openverse_fetch.sh" --id "..." --query "..." --target {...}/assets/img --credits {...}/assets/credits.json
  done
fi

# 4. WebP conversion (Python only — no shell equivalent)
if [ -n "$PY" ] && [ -d "{project-name}/assets/photos/source" ]; then
  $PY "<skill-dir>/scripts/webp_convert.py" --src {project-name}/assets/photos/source --dst {project-name}/assets/img
  # If conversion fails or Pillow can't install, the script copies originals.
fi
# If Python isn't available, the user's photos stay in their original format
# (JPG/PNG). The HTML references will use those extensions instead of .webp.
# This is fully acceptable; modern browsers all support JPG/PNG.
```

The user does **not** see these commands or run them. Claude runs them in the background.

**Critical:** before generating HTML/CSS/JS, check whether image conversion produced WebP files or kept originals. Reference the actual extensions in the HTML (`.webp` if converted, otherwise `.jpg`/`.png`).

### Step 5 — Generate code

Generate `index.html`, `styles.css`, `main.js`, `lib/manifest.js` (and any extra page) following:
- The chosen archetype's recipe (`reference/02-archetypes.md`).
- The mandatory rules from gotchas (`reference/04-critical-gotchas.md`).
- The convention rules (`reference/01-stack-and-conventions.md`).
- The deployment strategy (`reference/10-deployment-and-cache.md`).

**Mandatory generation rules** (do these without prompting):
1. **Use IIFE pattern, not ES modules.** No `import`/`export` keywords. Classic `<script defer>` tags + `window.__BRAND__`.
2. **Add `?v=YYYYMMDD` cache-buster** to every `<link>` and `<script src>` in HTML (use today's date).
3. **Default to native scroll** (`scroll-behavior: smooth` in CSS + `window.scrollTo` for anchors). Only include Lenis if the archetype explicitly demands inertia.
4. **Defensive CSS for `.reveal[data-split]`**: include `.reveal[data-split] { opacity: 1; transform: none; }` so the JS conflict can't make text invisible.
5. **Copy the `.htaccess`** from `templates/htaccess.template` to the project root.

### Step 6 — Verify

Run the verifier:

```bash
python "<skill-dir>/scripts/verify_project.py" --project {project-name}
```

It checks: dead links, mixed image formats, `<script type="module">` (forbidden), bad threshold values in IntersectionObserver, missing safety nets in splash, and more.

If verifier reports issues → fix them silently and re-run.

### Step 7 — Launch local preview server

Before handing off, **start a local HTTP server in the background** so Claude Code's Preview panel can render the site with all CSS, JS, and effects working (file:// blocks `fetch()` and some other behaviors).

Use the Bash tool with `run_in_background: true`:

```bash
cd {project-name} && python3 -m http.server 8765
```

If `python3` isn't available, fall back to `python -m http.server 8765`. If neither, tell the user to open `index.html` manually (most things will still work).

After the server starts, **navigate Claude Code's Preview panel to** `http://localhost:8765/`. The site renders with full effects: animations, fetch of `credits.json`, view transitions, etc.

### Step 8 — Hand off to user

Tell the user:
- The folder where the website is.
- That preview is already running at `http://localhost:8765/` (visible in the right panel).
- One sentence on how to deploy (drag the folder to Hostinger / Netlify / similar).
- Offer to make adjustments (copy, photos, color, page count) but do NOT push the user — they may want to walk away.

**Do not** lecture about the technical decisions. The user cares about the result, not the process.

---

## Hard rules — NEVER break

These are encoded in `reference/04-critical-gotchas.md` but worth highlighting up top:

1. **No `<script type="module">` with relative imports.** It breaks `file://`, breaks cache busting, breaks on some hosts. Use classic `<script defer>` + IIFE pattern. (See gotcha A.14.)
2. **`.htaccess` in every project root.** Copy from `templates/htaccess.template`. Without it, Hostinger serves stale JS/CSS for 30 days after every deploy. (See gotcha A.13 + `10-deployment-and-cache.md`.)
3. **`?v=YYYYMMDD` cache-buster** on every `<link>` and `<script>` in HTML. Bump on each deploy.
4. **Native scroll by default.** Lenis is opt-in only — fragile across Windows configs. Use `scroll-behavior: smooth` in CSS. (See gotcha B.1.4.)
5. **Defensive CSS for `.reveal[data-split]`.** Include the rule that anuls `opacity: 0` for split-text elements. JS-only fixes silently fail when JS is cached stale. (See gotcha A.4.5.)
6. **No npm dependencies in runtime.** Only files in `lib/`. Python scripts are dev-time only.
7. **Do not gate micro-interactions with `prefers-reduced-motion`.** Windows ships it ON. Only gate truly intrusive effects.
8. **All images converted to WebP.** Never mix `.jpg` / `.png` / `.webp` references.
9. **Hardcode critical content in HTML.** JS only enriches. If JS fails, the site still reads.
10. **Each `init*` wrapped in `safe(fn, name)` try/catch.** One failing init must not break the rest.
11. **IntersectionObserver threshold ≤ 0.05 + 6s safety timeout** that reveals anything still hidden.
12. **Splash with double safety net** (CSS animation 4.5s + JS hide).
13. **Idempotent mounts**: every dynamic mount checks `if (target.children.length > 0) return;`.
14. **Content first, animation second.** A slow-loading wow effect that hides text is a regression.
15. **No cursor trail of thumbnails by default.** It often reads as a visual bug, not an effect. (See gotcha C.11.5.)

---

## Quality bar — what "premium" means here

The output should pass these subjective tests:

- **First-screen wow.** When the user opens `index.html`, the first viewport must be visually arresting. Fade-in animation, type reveal, gradient mesh, hero image with parallax — something that says "this is not a template".
- **Effects feel intentional, not pasted.** Every animation has a reason. No effect duplicates another.
- **Mobile is not an afterthought.** The mobile layout is a different composition that works on its own — not a squashed desktop.
- **Copy is editorial.** No buzzwords. No "unlock", "transform", "secrets", "revolutionary". Sentences that a magazine editor would write.
- **Robustness > spectacularity** when in doubt. A solid web that's a bit less wow beats a broken showcase.

---

## Diversity mandate

The skill ships with three reference projects (Nómada, 911 Restaurante, The Gambit). They are EXAMPLES of quality, not templates to copy.

**If you find yourself writing code that mirrors one of them too closely, stop.** Pick a different archetype. Use a different effect from the catalog. Different layout topology. Different palette family. Read `reference/06-diversity-guardrails.md` for the explicit anti-monotony rules.

The user must NEVER feel "this looks like another web you made". Every site is a different solution.

---

## Skill files index

```
SKILL.md                                ← this file (entry point)
intake-template.md                      ← short script for asking the user
recommended-settings.json               ← optional pre-authorization for zero-prompt mode
reference/
  01-stack-and-conventions.md           ← file structure, IIFE pattern, script loading
  02-archetypes.md                      ← 10 archetypes (palette + tipo + effects per one)
  03-effects-catalog.md                 ← 40+ effects with copy-paste snippets
  04-critical-gotchas.md                ← errors learned from real projects
  05-image-and-asset-pipeline.md        ← Openverse, WebP, photos handling
  06-diversity-guardrails.md            ← anti-copy rules + rotation log
  07-windows-troubleshooting.md         ← reduced-motion + Windows quirks
  08-pre-deploy-checklist.md            ← final verification list
  09-environment-detection.md           ← Python/Bash detection + fallback strategy
  10-deployment-and-cache.md            ← Hostinger, .htaccess, cache busting strategy
templates/
  htaccess.template                     ← copy as `.htaccess` to every project root
scripts/
  openverse_fetch.py                    ← stock images (no API key) — Python
  openverse_fetch.sh                    ← Bash fallback (curl + grep parsing)
  webp_convert.py                       ← image pipeline (Pillow + auto-install)
  download_libs.py                      ← GSAP/ScrollTrigger to lib/ (Lenis/Three on demand)
  download_libs.sh                      ← Bash fallback (curl)
  verify_project.py                     ← post-generation sanity check
```

---

## Optional: zero-prompt mode for the user

By default, Claude Code asks the user to authorize each Bash command (download libs, fetch images, etc.). Roughly 5–10 prompts during a typical generation.

If the user wants **zero prompts**, recommend they copy the contents of `recommended-settings.json` (at the skill root) into their `.claude/settings.json` once. After that, the skill runs silently from start to finish — the user only sees:

> *"Creando tu web…"* → progress messages → *"Lista. Abre `index.html`."*

The patterns in `recommended-settings.json` are scoped to **only** the skill's own scripts plus a handful of safe helpers (`mkdir`, `ls`, `cp`, `grep`). Nothing destructive (`rm`, `mv`, network access outside the scripts) is pre-authorized.

To install the settings:
1. Open `~/.claude/settings.json` (or create it).
2. Merge the `permissions.allow` array from `recommended-settings.json`.
3. Restart Claude Code session if open.

For users who prefer to see each step, leave settings as-is and accept the prompts as they come.

---

## Final note for the assistant

Treat the user as a **non-technical client**. Their goal is a beautiful, working website they can show off and that doesn't break. Your goal is to give them that with minimum friction.

When in doubt:
- **Decide for them.**
- **Run the script silently.**
- **Default to robust over flashy.**
- **Show, don't lecture.**

If at the end of the process the user opens `index.html` and says *"wow"*, you've done it right.
