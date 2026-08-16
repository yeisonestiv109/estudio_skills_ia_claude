# Stack & Conventions

The non-negotiable technical rules. Same for every project, regardless of archetype.

---

## 1. Stack

| Layer | Tech | Why |
|---|---|---|
| Markup | HTML5 semantic | Works without JS for content |
| Style | CSS3 modern (custom properties, `clamp()`, `grid`, `@property`) | No preprocessor needed |
| Behavior | Vanilla JS, **classic scripts** (NOT modules) | Works on `file://`, FTP hosting, any environment |
| Animation | GSAP 3.13+ + ScrollTrigger | Industry standard, stable |
| Smooth scroll | Lenis 1.1+ | Replaces Locomotive |
| 3D (when needed) | Three.js r128 (CDN UMD) | Stable, works without modules |
| Fonts | Google Fonts via `<link>` | No font self-hosting hassle |
| Images | WebP via `assets/img/` | Universal modern browser support |

### Forbidden

- **No npm**, no `node_modules`, no `package.json` in the deliverable.
- **No build step**. No Vite, Webpack, Rollup, esbuild, Astro, Next.
- **No `<script type="module">` with relative imports**. Breaks `file://`.
- **No frameworks**. No React/Vue/Svelte/Solid/Qwik. Only vanilla JS.
- **No TypeScript** in the deliverable (write it as JS directly).
- **No CSS-in-JS**, no Tailwind, no PostCSS plugins. Plain `styles.css`.

### Allowed (only locally, never CDN at runtime)

Place these in `lib/` (downloaded once by `scripts/download_libs.py`):
- `lib/gsap.min.js` (~72 KB) — **always**
- `lib/ScrollTrigger.min.js` (~43 KB) — **always**
- `lib/lenis.min.js` (~13 KB) — **only when** the project explicitly demands inertia smooth scroll (rare; see below).
- `lib/three.min.js` (~600 KB) — only if archetype uses 3D.

Total runtime payload (without Lenis or 3D): ~115 KB.

**About Lenis:** the default for this skill is **native scroll** (`scroll-behavior: smooth` in CSS + `window.scrollTo`). Lenis is fragile across Windows configurations and adds tuning complexity that bites on real client machines. Only add Lenis if (a) the archetype demands Mac-style inertia AND (b) the budget allows multi-OS testing. See gotcha B.1.4 in `04-critical-gotchas.md`.

---

## 2. Folder structure (canonical)

```
project-name/
├── index.html                  ← always
├── <other-page>.html           ← optional: carta.html, about.html, blog.html…
├── styles.css                  ← single CSS file, organized by sections
├── main.js                     ← entry point, IIFE pattern
├── lib/
│   ├── gsap.min.js
│   ├── ScrollTrigger.min.js
│   ├── lenis.min.js
│   ├── three.min.js            ← only if archetype needs 3D
│   └── manifest.js             ← brand data: window.__BRAND__
├── tools/
│   └── (dev-time scripts, NOT shipped — Python or PowerShell)
└── assets/
    ├── img/                    ← all WebP, kebab-case names
    ├── photos/source/          ← user's original images (ignored at deploy)
    ├── credits.json            ← attribution metadata
    └── (favicon.ico / .svg)
```

**Notes:**
- `tools/` is dev-only. Tell the user they can ignore or delete it.
- `assets/photos/source/` keeps the user's originals. The pipeline writes WebP to `assets/img/`. Both stay; if the user wants a smaller deploy, they can delete `source/`.

---

## 3. Script load order in HTML

Always at the **end of `<body>`** (or in `<head>` with `defer`), always with `defer`, always in this order:

```html
<!-- libs first (defer keeps order) -->
<script defer src="lib/gsap.min.js"></script>
<script defer src="lib/ScrollTrigger.min.js"></script>

<!-- ONLY if the archetype explicitly opts in (rare) -->
<!-- <script defer src="lib/lenis.min.js"></script> -->

<!-- ONLY if 3D archetype -->
<script defer src="lib/three.min.js"></script>

<!-- brand data -->
<script defer src="lib/manifest.js"></script>

<!-- entry point — bump ?v= on every deploy -->
<script defer src="main.js?v=YYYYMMDD"></script>
```

The `?v=YYYYMMDD` cache-buster is mandatory for production deploys (see gotcha A.13). The `.htaccess` template handles cache headers, but the version string forces the first paint after deploy to fetch new code.

`defer` guarantees:
1. Scripts run **after HTML is parsed** but **before** `DOMContentLoaded`.
2. Scripts execute **in document order** even though they download in parallel.
3. Works on `file://`, hosting, CDN.

**Forbidden alternative:**
```html
<!-- ❌ DO NOT use type=module with relative imports -->
<script type="module" src="main.js"></script>
```
That breaks `file://` (CORS) and many cheap hostings serve `.js` with wrong MIME for modules.

---

## 4. IIFE pattern for JS files

Every JS file is an immediately-invoked function expression that exposes data via `window.__BRAND__` (one global, namespaced).

### `lib/manifest.js` — brand data only

```js
(function () {
  "use strict";
  window.__BRAND__ = {
    name: "Brand Name",
    tagline: "Short tagline",

    // Content arrays — anything dynamic
    products: [
      { id: "p-001", name: "Item", price: 12, photo: "assets/img/item-1.webp" },
      // ...
    ],
    testimonials: [/*...*/],
    faqs: [/*...*/],
    contact: { email: "hi@brand.com", phone: "+34 …", address: "…" }
  };
})();
```

### `main.js` — entry point

```js
(function () {
  "use strict";

  const data = window.__BRAND__ || {};
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Helpers (compact, reusable)
  const $ = (sel, scope) => (scope || document).querySelector(sel);
  const $$ = (sel, scope) => Array.from((scope || document).querySelectorAll(sel));
  const escHTML = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, c =>
    ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" })[c]);

  // Idempotent mounts — fill HTML if empty, never duplicate
  function mountProducts() {
    const target = $("[data-products]");
    if (!target || target.children.length > 0 || !data.products) return;
    target.innerHTML = data.products.map(p => `
      <article class="product">
        <img src="${escHTML(p.photo)}" alt="${escHTML(p.name)}" loading="lazy" />
        <h3>${escHTML(p.name)}</h3>
      </article>
    `).join("");
  }

  // Init functions — each isolated
  function initSplash() { /* ... */ }
  function initNav() { /* ... */ }
  function initReveals() { /* ... */ }
  function initTilt() { /* ... */ }
  // etc.

  // Safe wrapper — one failure doesn't break the rest
  function safe(fn, name) {
    try { fn(); } catch (e) { console.warn("[" + name + "] failed:", e); }
  }

  function boot() {
    // 1. Mounts first (idempotent — only fills if HTML empty)
    safe(mountProducts, "mountProducts");

    // 2. Inits that don't need GSAP
    safe(initSplash, "initSplash");
    safe(initNav, "initNav");
    safe(initReveals, "initReveals");
    safe(initTilt, "initTilt");

    // 3. GSAP-dependent inits — gated by feature detection
    if (window.gsap && window.ScrollTrigger) {
      try { gsap.registerPlugin(ScrollTrigger); } catch (_) {}
      safe(initLenis, "initLenis");
      safe(initHeroParallax, "initHeroParallax");
      safe(initShowcasePinned, "initShowcasePinned");
    }

    document.documentElement.classList.add("is-ready");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
```

### Why this pattern works

- **No globals leaked** beyond `window.__BRAND__`.
- **One failure isolated** — `safe()` prevents cascade failure.
- **GSAP feature-detected** — if the CDN script fails to load, basic functionality still works.
- **Idempotent mounts** — running boot() twice doesn't duplicate content.

---

## 5. Naming conventions

| Type | Convention | Example |
|---|---|---|
| HTML files | kebab-case | `kyoto-detail.html` |
| CSS classes | kebab-case | `.hero-title`, `.nav-cta` |
| CSS custom properties | kebab-case + `--` | `--bg`, `--accent`, `--gutter` |
| JS variables / functions | camelCase | `mountProducts`, `initTilt` |
| JS constants (real consts) | UPPER_SNAKE | `const HOVERABLES = "..."` |
| Image files | kebab-case + WebP | `hero-vista.webp`, `plato-tataki.webp` |
| Data attributes | `data-<purpose>` kebab | `data-products`, `data-tilt` |

---

## 6. CSS organization (single file, sectioned)

`styles.css` is a single file with clearly demarcated sections:

```css
/* =============================================================
   1. Tokens (custom properties, @property)
   ============================================================= */
:root { /* ... */ }

/* =============================================================
   2. Reset & base
   ============================================================= */
*, *::before, *::after { box-sizing: border-box; margin: 0; }

/* =============================================================
   3. Utilities (skip-link, sr-only, container)
   ============================================================= */

/* =============================================================
   4. Typography (h1-h6, p, links, lists)
   ============================================================= */

/* =============================================================
   5. Components (.btn, .card, .form, .nav)
   ============================================================= */

/* =============================================================
   6. Sections (.hero, .showcase, .footer)
   ============================================================= */

/* =============================================================
   7. Effects (animations, transforms, keyframes)
   ============================================================= */

/* =============================================================
   8. Responsive (mobile-first, then breakpoints)
   ============================================================= */
@media (min-width: 720px) { /* ... */ }
@media (min-width: 1024px) { /* ... */ }
@media (min-width: 1280px) { /* ... */ }

/* =============================================================
   9. Reduced-motion (only INTRUSIVE effects, not all)
   ============================================================= */
@media (prefers-reduced-motion: reduce) {
  /* Only apply to: autoplay video, particles, parallax >40px, loops >4s */
  .hero-meta-dot { animation: none; }
  .particle-system { display: none; }
  /* Do NOT disable: tilts, hovers, fades, mesh, count-ups */
}
```

---

## 7. Google Fonts loading

Always with preconnect:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=…&display=swap">
```

Three families maximum:
1. **Display serif** (Fraunces, Cormorant, Playfair, EB Garamond, Italiana).
2. **Body sans** (Inter, Manrope, Söhne fallback).
3. **Mono / accent** (JetBrains Mono, IBM Plex Mono) — optional.

Plus Noto fonts when content is multi-script (kanji, arabic, devanagari, etc.).

---

## 8. Images: hero priority loading

```html
<head>
  <!-- Preload the hero image — first paint priority -->
  <link rel="preload" as="image" href="assets/img/hero.webp" fetchpriority="high">
</head>
```

```html
<!-- Hero img tag -->
<img src="assets/img/hero.webp" alt="…" fetchpriority="high" loading="eager">

<!-- All other images -->
<img src="assets/img/product-1.webp" alt="…" loading="lazy" decoding="async">
```

---

## 9. Reset minimum

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; }
html { -webkit-text-size-adjust: 100%; tab-size: 2; }
body {
  font-family: var(--sans);
  font-size: 16px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
  overflow-x: clip;          /* NOT 'hidden' — clip doesn't break sticky */
  overscroll-behavior-y: none;
}
img, svg, video { display: block; max-width: 100%; }
img { height: auto; }
button { font: inherit; color: inherit; cursor: pointer; border: 0; background: none; }
a { color: inherit; text-decoration: none; }
p { text-wrap: pretty; }
h1, h2, h3, h4 { text-wrap: balance; line-height: 1.05; letter-spacing: -0.02em; }
::selection { background: var(--accent); color: var(--cream); }

:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 3px;
  border-radius: 4px;
}

.skip-link {
  position: fixed; top: -100px; left: 1rem;
  padding: .6rem 1rem; background: var(--cream); color: var(--bg);
  z-index: 9999; border-radius: 8px; font-weight: 500;
}
.skip-link:focus { top: 1rem; }
```

---

## 10. Breakpoints

Always **mobile-first**. Use these and only these:

```css
/* Default: mobile (<540px) */

@media (min-width: 540px)  { /* large phone / small tablet */ }
@media (min-width: 720px)  { /* tablet portrait */ }
@media (min-width: 960px)  { /* tablet landscape / small laptop */ }
@media (min-width: 1280px) { /* laptop / desktop */ }
@media (min-width: 1600px) { /* large desktop — optional */ }
```

Do **not** invent custom breakpoints (`1024px`, `768px`, etc.). Five fixed steps cover all real cases.

---

## 11. Easings (use these, not raw `ease-out`)

```css
:root {
  --ease-out:  cubic-bezier(0.16, 1, 0.3, 1);     /* default, ALL hover transitions */
  --ease-in:   cubic-bezier(0.7, 0, 0.84, 0);
  --ease-soft: cubic-bezier(0.25, 0.46, 0.45, 0.94);
  --ease-bounce: cubic-bezier(0.34, 1.56, 0.64, 1);
}
```

For GSAP, use `"expo.out"` and `"power3.out"` as defaults. They match `--ease-out` visually.

---

## 12. Helpers placed in `main.js` (always)

```js
const $  = (sel, scope) => (scope || document).querySelector(sel);
const $$ = (sel, scope) => Array.from((scope || document).querySelectorAll(sel));
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const fineHover = matchMedia("(hover: hover) and (pointer: fine)").matches;
const escHTML = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, c =>
  ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" })[c]);
function safe(fn, name) { try { fn(); } catch (e) { console.warn("[" + name + "]", e); } }
```

---

## 13. HTML must work without JS

**Test before declaring done:** open the page with JS disabled (DevTools → Settings → Disable JS). The site must still:
- Show all content (heroes, products, menu, contact info, footer).
- Be navigable (anchors work, links work).
- Look acceptable (no broken layouts).

It's allowed to lose:
- Animations and reveals (content shows up immediately).
- Smooth scroll (it falls back to native).
- 3D scenes (canvas stays empty).
- Cursor effects.
- Forms with simulated submit (the user can still see the form fields).

It's NOT allowed to lose:
- Any **content** (texts, images, products, prices).
- Navigation.
- Page structure.

---

## 14. Page transitions (multi-page sites)

Use the **View Transitions API** for cross-page transitions (no library needed):

```css
@view-transition { navigation: auto; }
::view-transition-old(root),
::view-transition-new(root) {
  animation-duration: 0.6s;
  animation-timing-function: cubic-bezier(0.16, 1, 0.3, 1);
}
::view-transition-old(root) { animation-name: fadeOutUp; }
::view-transition-new(root) { animation-name: fadeInUp; }
@keyframes fadeOutUp { to { opacity: 0; transform: translateY(-12px); } }
@keyframes fadeInUp { from { opacity: 0; transform: translateY(12px); } }
```

```js
// Optional: opt-in via JS for browsers that need explicit trigger
document.addEventListener("click", e => {
  const a = e.target.closest("a[href]");
  if (!a || !shouldIntercept(a)) return;
  e.preventDefault();
  if (document.startViewTransition) {
    document.startViewTransition(() => { location.href = a.href; });
  } else {
    location.href = a.href;
  }
});
```

---

## 15. Final check before considering structure done

- [ ] No `<script type="module">` anywhere.
- [ ] No `import` / `export` keywords in any `.js` file.
- [ ] All scripts in `<head>` or end of `<body>`, all with `defer`, in correct order.
- [ ] `lib/manifest.js` exposes only `window.__BRAND__`.
- [ ] `main.js` is an IIFE.
- [ ] Every `init*` is wrapped in `safe()`.
- [ ] No `.jpg` or `.png` references in HTML/CSS/JS — all `.webp`.
- [ ] `assets/img/` is the only image folder referenced.
- [ ] Skip-link present, focus-visible styled, alt-text on every image.
