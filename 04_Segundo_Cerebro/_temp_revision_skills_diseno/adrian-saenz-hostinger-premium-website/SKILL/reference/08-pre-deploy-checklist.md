# Pre-deploy Checklist — run BEFORE telling the user it's done

Before declaring the website ready, walk through this checklist. If anything fails, fix and re-check.

The verifier script (`scripts/verify_project.py`) automates many of these, but some require manual inspection.

---

## 1. Robustness (must-pass)

- [ ] **No `<script type="module">`** anywhere. `grep -rn 'type="module"' --include="*.html"` returns nothing.
- [ ] **No `import` / `export`** keywords in any `.js` file in `lib/` or root. `grep -rn '^import\|^export' --include="*.js"` returns nothing (excluding scripts/ and node_modules/).
- [ ] **All scripts loaded with `defer`**, in correct dependency order.
- [ ] **`window.__BRAND__`** namespace is the only global from `lib/manifest.js`.
- [ ] **`main.js` is an IIFE** wrapping all logic.
- [ ] **Each `init*` is wrapped in `safe()` try/catch.**
- [ ] **No image references in `.jpg` / `.png`** — all WebP. `grep -rn '\.jpg\|\.png' --include="*.html" --include="*.css" --include="*.js"` returns nothing (excluding HANDOFF / README).
- [ ] **`assets/img/` is the only image folder** referenced in production code.
- [ ] **Splash has both CSS animation safety net (4.5s) and JS hide.**
- [ ] **IntersectionObservers use `threshold ≤ 0.05`** + 6s `setTimeout` safety to reveal anything still hidden.
- [ ] **Mounts are idempotent** — running `boot()` twice doesn't duplicate content.
- [ ] **Carousels with horizontal scroll have `overflow-y: visible`** explicitly.
- [ ] **No `gsap.from` on children inside pinned ScrollTrigger**.
- [ ] **Sticky elements have no ancestor with `overflow: hidden`** (`overflow: clip` is OK).
- [ ] **Forms have `novalidate`** + JS validation + `preventDefault`.
- [ ] **No `console.error` in browser console** when loading the site.
- [ ] **No 404 in Network tab** for `assets/`, `lib/`, fonts.

## 2. Behavior under reduced-motion

Simulate via DevTools → Rendering → Emulate `prefers-reduced-motion: reduce`. Reload.

- [ ] **Hover effects still happen** (color, scale, shadow).
- [ ] **Cards still tilt** (subtle).
- [ ] **Smooth scroll still smooth** (just shorter duration).
- [ ] **Reveals on scroll still appear** (faster, but appear).
- [ ] **Marquee still moves**.
- [ ] **Mesh gradients still animate slowly**.
- [ ] **Variable font breathing still subtle**.
- [ ] **Count-ups still count up**.

What MUST be off:
- [ ] **Hero autoplay video paused** (or replaced by poster).
- [ ] **Particle system not visible**.
- [ ] **Strong parallax (>40px) reduced or off**.
- [ ] **Infinite spinners off**.

## 3. Behavior with JavaScript disabled

DevTools → Settings → Disable JavaScript. Reload.

- [ ] **All hero content visible** (headline, subtitle, CTAs).
- [ ] **All product / card content visible**.
- [ ] **All sections present** with their content.
- [ ] **Contact info visible**.
- [ ] **Footer fully present**.
- [ ] **Navigation works** (anchor links scroll, multi-page links navigate).
- [ ] **Layout not broken** (no overlapping elements, no missing backgrounds).
- [ ] **Forms have visible inputs** (even if submit doesn't simulate without JS).

## 4. Behavior on `file://` (double-click `index.html`)

- [ ] **Opens directly in browser** by double-clicking.
- [ ] **All content renders identically** to HTTP serving.
- [ ] **No CORS errors** in console.
- [ ] **All images load** (paths are relative, no leading `/`).
- [ ] **Fonts load** (Google Fonts work over file://).

## 5. Mobile / touch (DevTools device emulation)

iPhone 12 Pro, Galaxy S20, iPad Mini.

- [ ] **No horizontal overflow** (don't see horizontal scrollbar).
- [ ] **Hamburger menu works** (opens, closes, navigates).
- [ ] **Forms accessible** (inputs focusable, labels readable, submit visible).
- [ ] **Hero readable** (no text cut off).
- [ ] **Images proportional** (no awkward stretching).
- [ ] **Touch interactions work** (tap to expand, swipe carousels).
- [ ] **No hover-only critical interactions** (tooltips that disappear on tap).
- [ ] **`100svh` used for hero** (no jump when iOS URL bar appears).

## 6. Cross-browser quick check

If possible, test in:

- [ ] **Chrome / Edge** (Chromium) — primary target.
- [ ] **Safari** (or WebKit responsive in DevTools) — second target.
- [ ] **Firefox** — third target.

Look for:
- Different rendering of `backdrop-filter` (should have solid fallback).
- Different `100vh` behavior (Safari).
- Different font rendering (should look acceptable in all).
- Different scroll smoothness (Lenis should normalize).

## 7. Visual quality bar

This is subjective but mandatory:

- [ ] **First viewport "wow"**: opening the site immediately conveys premium quality. Editorial type, intentional layout, hero image / 3D / gradient that says "studio-grade".
- [ ] **No template feel**: nothing about the site looks like a Wordpress / Wix / Squarespace template.
- [ ] **Effects feel intentional**: every animation has a reason. No effect duplicates another.
- [ ] **Copy is editorial**: no buzzwords ("unlock", "transform", "secrets", "revolutionary"). Sentences a magazine editor would write.
- [ ] **Whitespace respected**: not packed. Sections breathe.
- [ ] **One signature effect**: when asked "what's the cool thing about this site", you can name ONE specific effect.
- [ ] **Mobile composition is intentional**, not a squashed desktop.

## 8. Accessibility (WCAG-AA minimum)

- [ ] **Skip-link** at start of body, focusable.
- [ ] **`:focus-visible`** styled (visible outline, not removed).
- [ ] **`alt` attribute** on every `<img>` (descriptive, or empty if purely decorative).
- [ ] **`aria-hidden="true"`** on decorative elements (cursor, mesh, grain).
- [ ] **`aria-label`** on icon-only buttons / links.
- [ ] **Form `<label>`** associated with every input.
- [ ] **Contrast** — body text 4.5:1 minimum, large text 3:1 minimum.
- [ ] **Headings semantic** — exactly ONE `<h1>` per page, `<h2>` for sections, etc.
- [ ] **Keyboard navigation** — Tab through the site, all interactive elements reachable.
- [ ] **Modal traps focus** when open (Cmd+K palette, mobile menu).

## 9. Performance (Lighthouse)

Run Lighthouse (DevTools → Lighthouse → Performance + Accessibility + Best Practices). Targets:

- [ ] **Performance** ≥ 85 on mobile (90+ on desktop).
- [ ] **Accessibility** ≥ 95.
- [ ] **Best Practices** ≥ 95.
- [ ] **SEO** ≥ 90.

If Performance is below 80, common culprits:
- Hero image too big → reduce.
- All images loaded eagerly → use `loading="lazy"`.
- Render-blocking CSS → already mitigated by single CSS file.
- JavaScript blocking → already mitigated by `defer`.
- Web fonts loading → already mitigated by `display=swap` + preconnect.

## 10. Final asset checks

- [ ] **Total project size** < 8 MB (excluding `assets/photos/source/`).
- [ ] **`assets/img/`** < 4 MB total.
- [ ] **No image > 250 KB** except hero (which is preloaded).
- [ ] **`lib/` size** < 200 KB (gsap + ScrollTrigger + Lenis = ~128 KB; +Three.js if used = ~728 KB).
- [ ] **Hero image preloaded** with `<link rel="preload">` and `fetchpriority="high"`.

## 11. Multi-page consistency (if applicable)

For multi-page sites:

- [ ] **Same nav / footer** on every page.
- [ ] **Same `manifest.js`** loaded.
- [ ] **Same `main.js`** loaded.
- [ ] **`window.__BRAND__` data** the same across pages.
- [ ] **View Transitions API** transitions between pages (if using).
- [ ] **Each page has a unique `<title>` and meta description.**

## 12. Credits & attribution (if using Openverse)

- [ ] **`creditos.html` page** exists and renders the full credits list.
- [ ] **`assets/credits.json`** is valid JSON, all entries have required fields.
- [ ] **Footer link** to credits is visible (small but present).
- [ ] **All BY/BY-SA images** have full attribution (author + license + link).
- [ ] **No `by-nc-*`** images (non-commercial).

## 13. Hand-off to user

Before sending the user the project, prepare:

- [ ] **Brief message** explaining what they got and how to deploy.
- [ ] **One-sentence instructions**: "Open `index.html` to preview locally. Drag the entire folder to Hostinger File Manager to deploy."
- [ ] **Optional**: a short note about what to customize (e.g., "If you want to change the email address or add more products, edit `lib/manifest.js`").

Don't lecture them on technical decisions. They want results.

---

## Automated verification

The skill ships with `scripts/verify_project.py`. Run it before manual checks:

```bash
python "<skill-dir>/scripts/verify_project.py" --project {project-name}
```

It catches:
- Module imports that should be classic scripts.
- Mixed image format references.
- Missing safety nets in splash.
- Bad threshold values in IntersectionObserver.
- Files referenced but not present.
- HTML structural issues (multiple h1, missing alt, etc.).
- JSON validity in `credits.json`.

Run it after every significant change. Fix all reported issues before declaring done.

---

## TL;DR — the 12-point release gate

1. ✅ No module imports.
2. ✅ All WebP.
3. ✅ Reduced-motion only kills intrusive effects.
4. ✅ Site works with JS disabled.
5. ✅ Site works on `file://`.
6. ✅ Mobile composition is intentional.
7. ✅ Cursor doesn't appear in (0,0) at load.
8. ✅ Splash has CSS safety net.
9. ✅ One signature effect, 4–5 effects total.
10. ✅ All animations under reduced-motion still happen for non-intrusive ones.
11. ✅ `verify_project.py` passes.
12. ✅ First-screen wow factor present.

If all 12 pass, hand off to the user.
