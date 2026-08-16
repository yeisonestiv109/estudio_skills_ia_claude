# ⚠️ Critical Gotchas — read before writing code

Every gotcha here is a **real bug** that appeared during development of one of the three reference projects. They tend to recur. The skill must internalize them and apply preventively.

Format for each: **symptom → root cause → solution**.

---

## TIER A — Will break the website silently if ignored

### A.1 ❌ NEVER `<script type="module">` with relative imports

**Symptom:** the user opens the site by double-clicking `index.html` (file:// protocol). The dynamic content doesn't appear. Menu blank, products empty. Console says "CORS error" or nothing at all.

**Root cause:** ES modules require HTTP origin. `file://` blocks them by default in Chrome / Edge / Safari.

**Solution:** **Always** use classic `<script defer>` + IIFE pattern. NEVER `import` / `export` keywords in the deliverable code.

```html
<!-- ✅ CORRECT -->
<script defer src="lib/gsap.min.js"></script>
<script defer src="lib/manifest.js"></script>
<script defer src="main.js"></script>

<!-- ❌ FORBIDDEN -->
<script type="module" src="main.js"></script>
```

```js
// ✅ CORRECT — IIFE with global namespace
(function () {
  "use strict";
  window.__BRAND__ = { /* data */ };
})();

// ❌ FORBIDDEN — fails on file://
import { data } from "./data.js";
```

---

### A.2 ❌ `prefers-reduced-motion` killing micro-interactions

**Symptom:** macOS user sees the website beautifully animated. Windows user sees it dead and flat. Different machines show different sites.

**Root cause:** Windows ships `prefers-reduced-motion: reduce` ON by default in many configurations (especially business/edu installs). Linux + some accessibility tools too. If you gate every animation with `@media (prefers-reduced-motion: reduce)`, you produce a flat website for those users.

**Solution:** distinguish two types of animations:

| Type | Examples | Gate with reduced-motion? |
|---|---|---|
| **Intrusive** | Autoplay video, particle systems, parallax >40px shift, infinite loops <4s, big shake/bounce | ✅ YES |
| **Functional / micro** | Hover tilt 7°, color transitions, fades on scroll, smooth scroll, mesh gradient slow loop, scramble, magnetic, marquee slow, count-up | ❌ NO |

**Pattern:**

```css
/* CSS — only gate the truly intrusive */
@media (prefers-reduced-motion: reduce) {
  .hero-meta-pulse { animation: none; }
  .particles { display: none; }
  /* DO NOT add: tilt, hover, fade, mesh, count-up, button hover */
}
```

```js
// JS — same logic; effects always run, only specific ones gate
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

// ✅ Lenis: shorten duration, don't disable
const lenis = new Lenis({ duration: reduced ? 0.7 : 1.15, ... });

// ✅ Particles: skip entirely
if (reduced) return;

// ✅ Tilt, magnetic, scramble, etc.: NEVER gate
function initTilt() {
  if (matchMedia("(hover: none)").matches) return;  // gate by hover capability ONLY
  // ...
}
```

Linear, Vercel, Stripe **don't disable** their micro-interactions. Match them.

See `07-windows-troubleshooting.md` for the full discussion.

---

### A.3 ❌ Custom cursor renders at (0,0) before first mousemove

**Symptom:** "There's a black spot in the top-left corner of the page when I open it. It disappears when I move the mouse."

**Root cause:** the `.cursor-dot` and `.cursor-ring` have `position: fixed; top: 0; left: 0;`. Until the first `mousemove` event sets a transform, they render at (0,0).

**Solution:**

```css
.cursor {
  opacity: 0;        /* HIDDEN by default */
  transition: opacity .25s var(--ease-out);
}
.cursor.is-ready { opacity: 1; }
```

```js
let firstMove = false;
window.addEventListener("mousemove", e => {
  // ... position
  if (!firstMove) {
    firstMove = true;
    rx = e.clientX; ry = e.clientY;       // place ring at cursor immediately
    ring.style.transform = `translate3d(${rx}px, ${ry}px, 0)`;
    cursor.classList.add("is-ready");
  }
});
```

---

### A.4 ❌ `splitWords` / `splitChars` flattens `<br>` and `<em>`

**Symptom:** a headline `<h1>Lorem<br/>ipsum <em>dolor</em></h1>` after split becomes `Loremipsum dolor` — no line break, no italic.

**Root cause:** the implementation reads `el.textContent` (which strips HTML), then sets `el.innerHTML` to a flat join.

**Solution:** iterate `el.childNodes`, preserve `<br>` and inline elements:

```js
function splitWords(el) {
  el.setAttribute("aria-label", el.textContent.trim().replace(/\s+/g, " "));
  const wrap = text => text.split(/(\s+)/).map(w =>
    /^\s+$/.test(w) ? w : `<span class="split-word" aria-hidden="true">${escHTML(w)}</span>`
  ).join("");
  const html = Array.from(el.childNodes).map(node => {
    if (node.nodeType === 3) return wrap(node.textContent);
    if (node.nodeName === "BR") return "<br>";
    if (node.nodeType === 1) {
      const tag = node.tagName.toLowerCase();
      return `<${tag}>${wrap(node.textContent)}</${tag}>`;
    }
    return "";
  }).join("");
  el.innerHTML = html;
  return el.querySelectorAll(".split-word");
}
```

---

### A.4.5 ❌ Element with both `.reveal` AND `data-split` becomes invisible

**Symptom:** a paragraph or headline appears as a blank space. Its kicker / byline above and below render correctly, but the paragraph itself is gone — there's just empty white space.

**Root cause:** the element has BOTH:
- `.reveal` class — CSS rule sets `opacity: 0; transform: translateY(40px)` until `.is-visible` is added.
- `data-split="lines"` (or words/chars) — split-text wraps internal text and animates children with their own system.

The reveal handler **excludes** `[data-split]` elements (selector `.reveal:not([data-split])`), so `is-visible` is never added. The split-text handler animates children but doesn't touch the parent's opacity. Result: parent stays at `opacity: 0` forever while the children dance invisibly inside.

**Fix (DEFENSIVE — at the CSS level, doesn't depend on JS being fresh):**

```css
/* In styles.css, right after the .reveal rule */
.reveal[data-split] {
  opacity: 1;
  transform: none;
}
```

This **always** wins over the `.reveal { opacity: 0 }` rule (same specificity, declared later) and survives even if:
- The JS handler that removes `.reveal` is cached old.
- ES module imports load a stale `effects.js`.
- Any unknown bug prevents the class removal at runtime.

**Optional secondary defense (in JS):**

```js
// In initSplitText
targets.forEach(el => {
  if (el.classList.contains("reveal")) el.classList.remove("reveal");
  // ... split processing
});
```

**Why CSS-first matters:** in deploy environments (Hostinger, CDNs) where JS files can be cached aggressively, JS-only fixes silently fail when an old `.js` is served. CSS fixes apply as soon as the (separately versioned) stylesheet is fresh — much more reliable.

**Detection:** if a section has empty white space where text should be, inspect the element. If it has both `.reveal` and `data-split`, that's the bug.

### A.5 ❌ `mouseenter` / `mouseleave` aren't dispatchable in some preview environments

**Symptom:** in headless preview / sandbox, your tests of hover effects don't trigger via `dispatchEvent(new MouseEvent("mouseenter", ...))`.

**Root cause:** `mouseenter` / `mouseleave` are non-bubbling and some headless engines don't process them synthetically.

**Solution:** use `mouseover` / `mouseout` with `relatedTarget` check:

```js
card.addEventListener("mouseover", e => {
  if (!card.contains(e.relatedTarget)) onEnter();
});
card.addEventListener("mouseout", e => {
  if (!card.contains(e.relatedTarget)) onLeave();
});
```

This is universally compatible AND testable.

---

### A.6 ❌ Race condition with async-rendered cards

**Symptom:** you have 8 cards. The first 6 work (hover, scramble, tilt). The last 2 don't respond.

**Root cause:** cards are filled async (image fetch with limited concurrency). Your global `init*` functions run on a single setTimeout that fires before the last cards are in the DOM.

**Solution:** **idempotent + per-card binding**.

```js
// In bilingual.js or similar
function bindBilingual(root = document) {
  root.querySelectorAll("[data-bilingual]").forEach(el => {
    if (el.dataset.bilingualBound) return;          // ⚠️ Idempotent marker
    el.dataset.bilingualBound = "1";
    // ... attach listeners
  });
}
```

```js
// In main.js card render function
function fillCard(card, item) {
  card.innerHTML = `...`;
  bindBilingual(card);                              // ⚠️ Bind right away on this card
}
```

The idempotency mark allows multiple calls without duplicating listeners.

---

### A.7 ❌ `gsap.from` inside pinned ScrollTrigger leaves cards translucent

**Symptom:** in a horizontally-pinned showcase, the cards stay at low opacity forever, even after scrolling.

**Root cause:** `gsap.from(cards, { opacity: 0, scrollTrigger: ... })` inside a section that's already pinned by a parent ScrollTrigger creates a conflict. The internal trigger doesn't fire.

**Solution:** **don't animate child cards** inside pinned sections. Either:
- Use CSS reveal triggered by the section entering viewport.
- Don't animate at all — the horizontal scroll IS the animation.

```js
// ❌ AVOID
gsap.from(track.querySelectorAll(".card"), {
  opacity: 0, y: 40,
  scrollTrigger: { trigger: section, start: "top 80%" },
});

// ✅ BETTER — only the pin + translation
gsap.to(track, {
  x: () => -distance,
  scrollTrigger: { trigger: section, pin: true, scrub: 0.6 },
});
```

---

### A.8 ❌ IntersectionObserver threshold too high → image stays hidden

**Symptom:** large images at the bottom of the page never reveal. They stay at `opacity: 0` forever.

**Root cause:** threshold `0.18` requires 18% of the image to be visible. A 2000px-tall hero image may never reach that on tall screens.

**Solution:**

```js
const io = new IntersectionObserver(entries => {
  entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add("is-revealed"); io.unobserve(e.target); } });
}, {
  threshold: 0.01,                          // ⚠️ Almost any intersection
  rootMargin: "0px 0px -2% 0px",
});

// ⚠️ MANDATORY safety: at 6s, force-reveal anything still hidden
setTimeout(() => {
  document.querySelectorAll("[data-reveal]:not(.is-revealed)").forEach(el => {
    if (el.getBoundingClientRect().top < window.innerHeight) {
      el.classList.add("is-revealed");
    }
  });
}, 6000);
```

---

### A.9 ❌ Splash loader stuck if JS fails

**Symptom:** the user sees the splash logo forever. Site unusable.

**Root cause:** the JS that hides the splash failed (any error, network blocked, etc.).

**Solution:** **double safety net** — CSS animation + JS:

```css
.splash {
  /* ⚠️ Safety: hide automatically at 4.5s even if JS fails */
  animation: splashSafety .01s 4.5s forwards;
}
@keyframes splashSafety {
  to { opacity: 0; pointer-events: none; clip-path: inset(0 0 100% 0); }
}
```

```js
function initSplash() {
  const splash = document.querySelector("[data-splash]");
  if (!splash) return;
  const hide = () => splash.classList.add("is-out");
  if (document.readyState === "complete") setTimeout(hide, 600);
  else window.addEventListener("load", () => setTimeout(hide, 400));
  setTimeout(hide, 4000);   // additional safety
}
```

---

### A.10 ❌ Mixing `.jpg` / `.png` / `.webp` references

**Symptom:** some images load, some don't. Network tab shows 404s.

**Root cause:** during refactoring or copy-paste, image references end up in mixed formats. HTML says `.jpg`, JS data says `.webp`, CSS background says `.png`.

**Solution:** **always WebP**. After processing images, run:

```bash
grep -rn "\.jpg\|\.png" --include="*.html" --include="*.css" --include="*.js"
```

Should return nothing (except in HANDOFF.md / README.md).

---

### A.13 ❌ Hostinger / CDN serves stale JS and CSS for hours after upload

**Symptom:** the developer uploads new HTML/CSS/JS to Hostinger via FTP. They reload the page and **the bug is still there** even after `Ctrl+Shift+R` and clearing browser cache. Local preview works fine. The site online doesn't.

**Root cause:** Hostinger (and most cheap shared hostings + CDNs) serve static assets with `Cache-Control: max-age=2592000` (30 days) by default. Browsers and intermediate proxies cache the old version. Uploading new files doesn't invalidate the cache — the server keeps responding "use the version from 30 days ago".

**Symptom amplifier:** the user assumes "I uploaded the new file, it must be the new version" and chases imaginary bugs in code that's already correct.

**Fix #1 (mandatory) — `.htaccess` for Hostinger / Apache hosts:**

The skill ships a `.htaccess` template at `templates/htaccess.template`. **Always include it** in the project root. It tells the server:
- HTML / JS / CSS / JSON: `no-cache, must-revalidate` (validate every visit).
- Images / fonts: `max-age: 1 month` (cache long, they change rarely).

```apache
<IfModule mod_headers.c>
  <FilesMatch "\.(html|css|js|mjs|json)$">
    Header set Cache-Control "no-cache, must-revalidate"
  </FilesMatch>
  <FilesMatch "\.(webp|jpg|jpeg|png|svg|woff|woff2)$">
    Header set Cache-Control "public, max-age=2592000"
  </FilesMatch>
</IfModule>
```

**Fix #2 (mandatory) — cache-busting query in HTML:**

Even with `.htaccess`, the first visit after deploy may serve from the user's browser cache. Bust it explicitly:

```html
<link rel="stylesheet" href="styles.css?v=20260511" />
<script type="module" src="main.js?v=20260511"></script>
```

Bump the `?v=YYYYMMDD` (or hash) on **every deploy**. The browser treats it as a new URL → fresh download.

**Fix #3 — for ES modules with relative imports (see A.14):**

Cache-busting `?v=` on the HTML's `<script src>` does NOT propagate to internal `import './lib/effects.js'` calls. The `.htaccess` covers this, but if the user is on a hosting where `.htaccess` is ignored (some LiteSpeed configs), use the IIFE pattern (no imports) — see A.14.

**Verification:** after deploy, open DevTools → Network → reload. Look at the "Status" column for `styles.css` and `main.js`. If you see `200` with the new size, you're getting fresh files. If you see `(disk cache)` in gray, the browser is still serving stale.

### A.14 ❌ ES modules with relative imports cache-bust badly + break on `file://`

**Symptom A:** `index.html` loads `main.js?v=20260511` (fresh) but `main.js` does `import './lib/effects.js'` which loads the cached old version. Users see a hybrid: new HTML + old JS behavior.

**Symptom B:** developer / client double-clicks `index.html` to preview locally. The page loads but no dynamic content appears (cards empty, no scramble, no animations). Everything is silent — no error visible to a non-technical user.

**Root cause:**
- `<script type="module">` requires HTTP origin. Browsers block `import` over `file://` for security.
- Cache-busting query strings don't propagate to internal imports automatically.

**Solution: avoid ES modules in shipped code.**

Use the **IIFE pattern** (Immediately-Invoked Function Expression) with classic `<script defer>`:

```html
<!-- ✅ Robust everywhere: file://, FTP, CDN, edge -->
<script defer src="lib/gsap.min.js"></script>
<script defer src="lib/manifest.js"></script>
<script defer src="main.js"></script>
```

```js
// lib/manifest.js
(function () {
  "use strict";
  window.__BRAND__ = { /* data */ };
})();

// main.js
(function () {
  "use strict";
  const data = window.__BRAND__ || {};
  // ... all logic
})();
```

This pattern is documented in `01-stack-and-conventions.md` §4. The skill's templates use it by default — **never write ES modules in deliverables**.

**If a project already uses modules** (legacy or by mistake): the migration is mechanical:
1. Each `lib/*.js` file → wrap in `(function() { ... window.__BRAND__.X = X; })()` instead of `export`.
2. `main.js` → wrap in IIFE, replace `import` with reads from `window.__BRAND__`.
3. HTML scripts → `<script defer>` in dependency order.

---

## TIER B — Will produce buggy UX

### B.1 ❌ Carousel with `overflow-x: auto` inherits Y clip

**Symptom:** a horizontal carousel where cards have a decoration that sticks out (shadow, badge, comma mark). The decoration gets cut at the carousel border.

**Root cause:** `overflow-x: auto` defaults `overflow-y` to also clip.

**Solution:**

```css
.carousel-track {
  overflow-x: auto;
  overflow-y: visible;          /* ⚠️ EXPLICIT */
  padding-block: 2rem 2.5rem;   /* breathing room */
}
```

---

### B.1.4 ❌ Lenis is fragile across Windows configurations — prefer native scroll

**Symptom:** mouse wheel feels laggy / unresponsive / "stuck" on some Windows machines. Tweaking `lerp`, `wheelMultiplier`, `duration` doesn't fully fix it. Side scrollbar works fine.

**Root cause:** Lenis is great in theory but in practice has subtle interactions with:
- Windows trackpad drivers.
- High-DPI scaling (125%, 150%).
- Browsers that throttle wheel events differently (Edge vs Chrome).
- Battery saver / power throttling.
- Body / html `overflow` rules.

Tuning Lenis to feel right on every machine is a moving target. A configuration that's perfect on a MacBook can feel broken on a Surface Pro.

**Recommended default — native scroll:**

```html
<!-- Don't include lenis -->
<script defer src="lib/gsap.min.js"></script>
<script defer src="lib/ScrollTrigger.min.js"></script>
<script defer src="main.js"></script>
```

```css
/* In styles.css */
html {
  overflow-x: clip;
  scroll-behavior: smooth;        /* native smooth for anchors */
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
}
```

```js
// In main.js — anchor handling
function setupSmoothScroll() {
  document.addEventListener("click", e => {
    const a = e.target.closest('a[href^="#"]');
    if (!a) return;
    const id = a.getAttribute("href");
    if (!id || id === "#") return;
    const el = document.querySelector(id);
    if (!el) return;
    e.preventDefault();
    const navOffset = 80;
    window.scrollTo({
      top: el.getBoundingClientRect().top + scrollY - navOffset,
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
  });
  if (window.gsap && window.ScrollTrigger) {
    gsap.registerPlugin(ScrollTrigger);
  }
}
```

What you lose: the Mac-style inertia "premium feel".
What you gain: zero scroll bugs across machines, drivers, browsers, OS configurations.

**ScrollTrigger works identically with native scroll.** No special integration needed.

**When to actually use Lenis:** only if (a) the brand is so premium that the inertia is part of the identity (Resn-tier studios), and (b) you're committing to test on multiple Windows machines + iPhones + iPads + Android. For 95% of projects, native is the correct default.

If you do use Lenis, set `lerp: 0.12` and `wheelMultiplier: 1.2` and integrate with GSAP ticker (single rAF loop). Document explicitly in the project that Lenis is opt-in and may need re-tuning per client.

### B.1.5 ❌ Lenis wheel scroll feels broken — only side scrollbar works

**Symptom:** the user scrolls with mouse wheel and nothing happens / very laggy / stuck. Side scrollbar works fine.

**Root causes (often combined):**

1. **`body { overflow-x: hidden }`** — blocks Lenis wheel handling in some browsers. Replace with `overflow-x: clip`.
2. **Lenis `duration` + `easing` config** — `duration` is for `scrollTo()` programmatic calls. For continuous user wheel input, use `lerp` instead. Each wheel tick with `duration: 1.15` queues a 1.15s animation, fast inputs feel stuck.

**Fix both:**

```css
body { overflow-x: clip; }    /* not hidden — clip preserves Lenis + sticky */
html { overflow-x: clip; }
```

```js
const lenis = new Lenis({
  lerp: 0.1,                  // ✅ for wheel — responds immediately, smooths progressively
  smoothWheel: true,
  wheelMultiplier: 1,
  touchMultiplier: 2,
});

// Use duration ONLY for scrollTo:
lenis.scrollTo(target, { offset: -10, duration: 1.4 });
```

`lerp` and `duration` are mutually exclusive on the constructor. `lerp` is correct for natural wheel feel.

### B.2 ❌ Sticky element fails because ancestor has `overflow: hidden`

**Symptom:** `position: sticky` doesn't stick. Element scrolls normally.

**Root cause:** any ancestor with `overflow: hidden` (often `body` or `.container`) breaks sticky.

**Solution:**

```css
body { overflow-x: clip; }    /* ✅ clip preserves sticky */
/* ❌ overflow-x: hidden;     breaks sticky */
```

If you need to clip horizontally for visual reasons, `clip` doesn't break sticky. `hidden` does.

---

### B.3 ❌ Sticky figure with shorter height than content beside it leaves a hole

**Symptom:** in a 2-column layout, the sticky figure is 60vh, the text content is 140vh. After the figure unsticks, there's a 80vh empty space.

**Solutions (preferred order):**

1. **Convert to single-column editorial layout.** Header → wide figure → 3-column pillars below. No sticky needed.
2. Make the figure non-sticky, let both columns flow.
3. Last resort: add decorative content under the figure to fill the space.

---

### B.4 ❌ Hero title clamp too aggressive → letters cut at viewport edges

**Symptom:** the headline "Patagonia" becomes "Patago..." on a 1024px screen. One letter is sliced.

**Root cause:** `font-size: 7vw` without `text-wrap: balance` and without a max-width.

**Solution:**

```css
.hero-title {
  font-size: clamp(2.4rem, 7vw, 6.4rem);
  line-height: 0.98;
  text-wrap: balance;             /* ⚠️ MANDATORY */
  max-width: 18ch;                /* ⚠️ never too wide */
  margin-inline: auto;
}
```

Centered headlines work better than left-aligned for huge sizes. Centered + balance + max-width never breaks.

---

### B.5 ❌ Strip of cards wraps to 2 lines on mid-size viewports

**Symptom:** a row of 11 small cards looks great on desktop (1920) but at 1024 wraps to 2 lines and looks broken.

**Solution:**

```css
.strip-row {
  display: flex;
  flex-wrap: nowrap;          /* ⚠️ never wrap */
  gap: 0.6rem;
}
.strip-card {
  flex: 1 1 0; min-width: 0;  /* shrink as needed */
  max-width: 130px;
}
@media (max-width: 1023px) { .strip-card:nth-child(n+10) { display: none; } }
@media (max-width: 767px)  { .strip-card:nth-child(n+8)  { display: none; } }
@media (max-width: 539px)  { .strip-card:nth-child(n+6)  { display: none; } }
```

5 well-sized cards beats 11 cramped ones.

---

### B.6 ❌ Halo with `overflow: hidden` cut abruptly at section border

**Symptom:** a section with a radial-gradient halo behind text. The halo cuts at the section edge instead of fading.

**Root cause:** `overflow: hidden` clips the blurred halo.

**Solution:**

```css
.section {
  position: relative;
  /* NO overflow: hidden */
}
.section-halo {
  position: absolute;
  inset: -80% -10% -50% -10%;        /* ⚠️ extend generously beyond bounds */
  background: radial-gradient(45% 35% at 50% 50%, rgba(196,154,91,.5), transparent 75%);
  filter: blur(120px);
  pointer-events: none;
}
```

Adjacent sections naturally overlap the halo with their own backgrounds.

---

### B.7 ❌ Scramble flickers on rapid hover

**Symptom:** moving the cursor over scrambled text creates a buggy flicker — text changes too fast, never resolves.

**Root cause:** every `mouseenter` cancels the running RAF and starts a new scramble.

**Solution:** mark `animating = true` and ignore re-entries; remove `mouseleave` handler that resets:

```js
let animating = false;
el.addEventListener("mouseenter", () => {
  if (animating) return;     // ⚠️ ignore re-entries
  animating = true;
  // ... scramble RAF, on completion: animating = false;
});
// ⚠️ NO mouseleave handler
```

For bilingual scramble, add a queue (see Nómada bilingual.js).

---

### B.8 ❌ Hardcoded BG color in section breaks dark/light theme switcher

**Symptom:** sections look fine in dark theme, broken in light theme. White text on white background.

**Root cause:** sections set their own `background: var(--bg)` AND text colors with hardcoded values.

**Solution:** use semantic custom properties that update with `data-theme`:

```css
:root { --bg: #0e0b09; --text: #f2ebda; }
[data-theme="light"] { --bg: #faf7f0; --text: #1a1714; }
section { background: var(--bg); color: var(--text); }
```

NEVER hardcode `color: white` or `background: black`.

---

### B.9 ❌ Three.js renders flipped image (UV / FLIP_Y mismatch)

**Symptom:** image displacement shader flips the photo upside down or mirror.

**Root cause:** `gl.UNPACK_FLIP_Y_WEBGL = true` combined with UV.y already inverted in the vertex buffer = double flip.

**Solution:** **avoid WebGL distortion on hero photos in editorial contexts**. Use parallax + ambient zoom + chromatic hover instead. If absolutely needed: pick ONE — either `UNPACK_FLIP_Y` true with standard UVs, OR false with inverted UVs. Test on a known image before committing.

---

### B.10 ❌ `setSize` and `setPixelRatio` in wrong order

```js
// ❌ WRONG — framebuffer resized twice, blurry result
renderer.setSize(w, h);
renderer.setPixelRatio(dpr);

// ✅ CORRECT
renderer.setPixelRatio(dpr);
renderer.setSize(w, h);
```

---

### B.11 ❌ Multiple rAF loops (one per module)

**Symptom:** 3D scene runs at 30fps even on desktop. Devtools shows excessive script time.

**Root cause:** every module (cursor, parallax, particles, three-scene) has its own `requestAnimationFrame` loop.

**Solution:** **one** rAF loop. Each module registers an updater:

```js
window.TG = {
  updaters: [],
  addUpdater(fn) { this.updaters.push(fn); },
  start() {
    function loop(t) {
      window.TG.updaters.forEach(fn => fn(t));
      renderer.render(scene, camera);
      requestAnimationFrame(loop);
    }
    requestAnimationFrame(loop);
  }
};

// in cursor.js
window.TG.addUpdater(t => { /* update cursor */ });
```

---

### B.12 ❌ Backdrop-filter without solid fallback

**Symptom:** glass cards look great in Chrome, become transparent in older Firefox / browsers without `backdrop-filter` support. Text mixes with background.

**Solution:**

```css
.glass-card {
  /* SOLID FALLBACK first */
  background: rgba(255,255,255,0.7);
  border: 1px solid rgba(255,255,255,0.3);
}
@supports (backdrop-filter: blur(20px)) {
  .glass-card {
    background: rgba(255,255,255,0.45);
    backdrop-filter: blur(20px) saturate(180%);
    -webkit-backdrop-filter: blur(20px) saturate(180%);
  }
}
```

---

## TIER C — Will surprise you (rare but real)

### C.1 ❌ `100vh` jumps in iOS Safari

**Symptom:** the hero "jumps" by ~80px when the user scrolls (Safari's URL bar appears/disappears).

**Solution:** use `100svh` (small) or `100dvh` (dynamic):

```css
.hero {
  min-height: 100vh;     /* fallback */
  min-height: 100svh;    /* small viewport — always visible area */
}
```

---

### C.2 ❌ Form submit during `is-sending` state with magnetic effect

**Symptom:** while the form sends, the button still moves toward cursor. Confusing.

**Solution:** disable magnetic during sending:

```css
.cta-form.is-sending button[type="submit"]:hover {
  transform: none;
}
```

Or: don't put magnetic on form submit buttons. Use pop-up hover instead (see catalog 7.1).

---

### C.3 ❌ `position: fixed` inside a parent with `transform` becomes relative to that parent

**Symptom:** in a showcase iframe with a wrapper that has `transform: scale()`, the fixed canvas is no longer relative to viewport — it scales with the wrapper.

**Solution:** for showcases / embeds, the wrapper with `transform` must contain the entire iframe, not the canvas as a child of the wrapper.

---

### C.4 ❌ `outputEncoding` not set in Three.js → hex colors look washed

**Symptom:** the gold `#c9a961` in materials renders as a dull blue-gray.

**Solution:**

```js
renderer.outputEncoding = THREE.sRGBEncoding;       // r128–r150
// renderer.outputColorSpace = THREE.SRGBColorSpace; // r150+
```

---

### C.5 ❌ Loading Three.js after the setup script

```html
<!-- ❌ WRONG ORDER -->
<script src="js/three-setup.js"></script>     <!-- uses THREE -->
<script src="lib/three.min.js"></script>

<!-- ✅ CORRECT -->
<script src="lib/three.min.js"></script>
<script src="js/three-setup.js"></script>
```

---

### C.6 ❌ Cards with conic-gradient border showing visible seam

**Symptom:** the conic gradient border shows a hard line where 0deg meets 360deg.

**Solution:** make the gradient end with the same color it starts with:

```css
background: conic-gradient(from var(--angle),
  var(--accent), transparent 30%, var(--accent) 100%);
```

---

### C.7 ❌ Sticky section labels showing under nav

**Symptom:** the section number / label stays at top of viewport when scrolling, but is partially hidden by the sticky nav.

**Solution:** add `top` offset equal to nav height:

```css
.section-label {
  position: sticky;
  top: 80px;            /* ⚠️ match nav height */
}
```

---

### C.8 ❌ `text-wrap: balance` shows different on first paint vs JS-modified

**Symptom:** the headline looks balanced initially, then jumps to a different layout when JS modifies its content (e.g., split text).

**Solution:** if you split text, do it before the page is interactive (synchronously in DOMContentLoaded), OR set the parent to `text-wrap: pretty` instead (less aggressive).

---

### C.9 ❌ Form validation doesn't trigger on `requestSubmit`

**Symptom:** programmatically calling `form.requestSubmit()` doesn't run native validation.

**Solution:** call `reportValidity()` first:

```js
if (!form.reportValidity()) return;
form.requestSubmit();
```

---

### C.10 ❌ `<dialog>` not opening or closing as expected

**Symptom:** modal opens but Escape doesn't close it; or closing it doesn't return focus.

**Solution:** use the modern API:

```js
dialog.showModal();    // not .show() — modal blocks background
dialog.close();        // returns focus to trigger automatically
```

---

### C.11 ❌ User uploads `.heic` photos (iPhone)

**Symptom:** the image conversion script fails on `.heic` files.

**Solution:** the WebP converter in `scripts/webp_convert.py` includes `.heic` support via Pillow's `pillow-heif` plugin. If not available, the script logs a warning and skips those files. Tell the user: "Tu cámara guarda en HEIC. Si quieres usar esas fotos, conviértelas a JPG/PNG primero o pasa esto al chat".

---

### C.11.5 ⚠ Cursor trail (thumbnails following mouse) often reads as "buggy"

**Symptom:** when the user moves the cursor over a section that has a "trail of thumbnails following the mouse", their reaction is often: *"hay un bug visual, las fotos se quedan superpuestas"* (visual bug, photos get stacked).

**Root cause:** the trail effect leaves photos in the DOM for ~1 second per spawn while they fade out. With moderate cursor movement, 4–8 photos pile up overlapping the section, looking like glitched render of the page itself rather than an intentional effect.

**Recommendation:**
- **Don't include cursor trail by default.** It's a high-effort, niche-result feature that polarizes (some love it, most find it noisy).
- If you do include it, scope it to a deliberate "wow moment" — a single section explicitly framed as interactive playground, not a content section users want to read.
- Reduce spawn density (`SPAWN_DISTANCE: 120` instead of 70) and total trail length (max 4–5 thumbnails, not 10).
- Always include a way to disable it (data attribute opt-in, not opt-out).

For most premium webs, **subtle hover effects on the cards themselves** (tilt + shadow + chromatic) achieve more wow with less risk.

### C.12 ❌ Lenis breaks scrollIntoView

**Symptom:** clicking an anchor link makes the page jump abruptly instead of smoothly scrolling.

**Solution:** intercept anchor clicks and use `lenis.scrollTo()`:

```js
document.addEventListener("click", e => {
  const a = e.target.closest('a[href^="#"]');
  if (!a) return;
  const id = a.getAttribute("href");
  if (!id || id === "#") return;
  const el = document.querySelector(id);
  if (!el) return;
  e.preventDefault();
  if (window.lenis) window.lenis.scrollTo(el, { offset: -80, duration: 1.2 });
  else window.scrollTo({ top: el.getBoundingClientRect().top + scrollY - 80, behavior: "smooth" });
});
```

---

## TIER D — Code quality / maintainability

### D.1 Wrap every `init*` in `safe(fn, name)`

Without this, one failing init breaks the rest of the boot.

```js
function safe(fn, name) { try { fn(); } catch (e) { console.warn("[" + name + "]", e); } }

function boot() {
  safe(initSplash, "initSplash");
  safe(initNav, "initNav");
  safe(initReveals, "initReveals");
  // ...
}
```

### D.2 Mounts must be idempotent

```js
function mountProducts() {
  const target = document.querySelector("[data-products]");
  if (!target || target.children.length > 0) return;   // ⚠️ already filled
  target.innerHTML = data.products.map(...).join("");
}
```

### D.3 Hardcode critical content in HTML; JS only enriches

If JS fails for any reason, the user must still see content. Hardcode everything important. Use JS for animations and polish only.

```html
<!-- ✅ HTML has 8 products visible -->
<div class="grid" data-products>
  <article><img src="..."><h3>Item 1</h3></article>
  <article><img src="..."><h3>Item 2</h3></article>
  <!-- 6 more -->
</div>
```

```js
// JS only animates them — doesn't generate them
function initRevealCards() {
  document.querySelectorAll("[data-products] article").forEach(card => {
    // attach IntersectionObserver
  });
}
```

If your data is huge / dynamic, generate the HTML at build time with a Node script (`tools/generate-html.mjs`), not at runtime.

---

## Quick reference — the 12 commandments

1. **No `<script type="module">` with relative imports.**
2. **Don't gate micro-interactions with `prefers-reduced-motion`.**
3. **Cursor `opacity: 0` until first mousemove.**
4. **Split-text iterates childNodes (preserves `<br>`).**
5. **Use `mouseover/mouseout` + relatedTarget, not `mouseenter/mouseleave`.**
6. **Bind listeners per-element on render (not via global setTimeout).**
7. **Don't `gsap.from` children inside a pinned ScrollTrigger.**
8. **IntersectionObserver: threshold ≤ 0.05 + 6s safety net.**
9. **Splash with double safety (CSS animation + JS).**
10. **All images WebP. Grep before declaring done.**
11. **Wrap every `init*` in `safe()` try/catch.**
12. **Hardcode content in HTML, JS only enriches.**

If you respect these 12, you avoid 95% of the bugs that historically plague this kind of project.
