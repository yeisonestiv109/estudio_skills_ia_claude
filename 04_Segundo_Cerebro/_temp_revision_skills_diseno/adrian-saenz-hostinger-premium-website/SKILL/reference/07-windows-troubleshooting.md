# Windows / Browser Configuration Troubleshooting

The #1 reason a non-technical user opens the website you generated and says **"it looks dead"** is that their Windows ships with `prefers-reduced-motion: reduce` ON by default. Many other configuration quirks compound this.

This document is the playbook to make websites work consistently across the wild variety of end-user setups.

---

## 1. The headline problem: `prefers-reduced-motion` on Windows

### What's happening

Windows 10 / 11 has a setting called **"Show animations in Windows"** under Accessibility → Visual Effects.

- In **Windows 10** Pro / Education / Enterprise builds: this is OFF in many corporate / business installs.
- In **Windows 11**: more often ON, but still varies.
- In some pre-installed Windows configurations from manufacturers (Lenovo Vantage, Dell, HP custom settings) it gets toggled OFF without user awareness.
- Power-saving modes can disable it temporarily.
- Some browsers (Edge, Chrome) read this OS preference and translate it to `prefers-reduced-motion: reduce`.

**Net effect:** the user did NOT explicitly request "less motion". The OS or vendor turned it off and the browser tells the website "user wants less motion".

### Why this kills our websites

If we gate every animation with `@media (prefers-reduced-motion: reduce)`, we produce a "flat" website for those users. Tilt cards don't tilt. Scrolls jump instead of smoothing. Scroll-reveal flashes content immediately. Marquees freeze. The whole **wow factor** disappears.

The user will say:
> "I open this on my PC and nothing moves. It's plain."

And rightly so — they didn't ask for accessibility, the OS just had a default they didn't touch.

### The solution: distinguish intrusive vs functional motion

Adopt this taxonomy:

| Type | Examples | Behavior with reduced-motion |
|---|---|---|
| **Intrusive** | Autoplay video looping in hero, particle systems (50+ moving dots), parallax shifts >40px, infinite spinners, big bounce animations, hard shake/vibration, infinite typing/scramble loops | **Disable** entirely or strongly reduce |
| **Smooth scroll** | Lenis, native smooth | **Shorten** duration to ~0.5–0.7s, don't disable entirely |
| **Functional UI** | Hover state changes, tilt 7°, button lift, color transitions, fade-in on scroll, mesh gradient slow loop, scramble on hover, count-up | **Always run** — these aren't intrusive, they're feedback |

### Code pattern

```css
/* CSS: only target genuinely intrusive effects */
@media (prefers-reduced-motion: reduce) {
  /* HERO video → freeze */
  .hero-video { animation-play-state: paused; }

  /* Particles canvas → hide */
  .particles { display: none; }

  /* Pulse infinite indicator → off */
  .live-dot { animation: none; }

  /* Bouncy decorations → off */
  .bouncy-arrow { animation: none; }

  /* DO NOT add: */
  /* .card { transition: none; } ❌ kills hover entirely */
  /* * { animation: none !important; } ❌ kills EVERYTHING */
}
```

```js
// JS: same logic
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

// Lenis: shorter, not off
const lenis = new Lenis({
  duration: reduced ? 0.7 : 1.15,    // ✅ correct
  // duration: reduced ? 0 : 1.15,    // ❌ wrong — disables smoothness
});

// Particles: skip entirely
function initParticles() {
  if (reduced) return;
  // ...
}

// Tilt: never gate by reduced-motion
function initTilt() {
  if (matchMedia("(hover: none)").matches) return;  // gate by hover capability ONLY
  // ...
}
```

### Verification — how to test

In Chrome/Edge DevTools:
1. F12 → ⋮ menu → More tools → **Rendering**.
2. Find "Emulate CSS media feature `prefers-reduced-motion`".
3. Set to **`reduce`**.
4. Reload the page.

Verify:
- Hover effects still happen.
- Scroll still feels smooth (just shorter duration).
- Cards still tilt slightly.
- Page reveals still fade in.
- Marquee still moves.

If anything noticeable disappears, you're gating too aggressively.

---

## 2. Other Windows-specific quirks

### 2.1 High-DPI scaling (125%, 150%, 200%)

Many laptops ship at 125% or 150% DPI scaling. This affects:

- **`devicePixelRatio` returns 1.25, 1.5, 2.0**, etc.
- Three.js needs `setPixelRatio(Math.min(devicePixelRatio, 2))` — capping at 2 prevents hi-DPI laptops from rendering 4× pixels.
- Particle systems should also cap DPR for performance.
- Custom cursor: `width: 32px` is a CSS pixel — 40px on a 125% scaled laptop. Don't worry about this; CSS pixels are meant to scale.

```js
const dpr = Math.min(devicePixelRatio || 1, 2);   // cap at 2 always
```

### 2.2 Edge browser default font is "Segoe UI"

On Windows + Edge, system-ui fallback resolves to **Segoe UI**, which has a different metric than macOS's San Francisco. Headlines may look slightly different.

**Solution:** always specify Inter (or your chosen sans) as the primary, with system-ui as the fallback only:

```css
font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
```

Inter loads from Google Fonts and looks consistent across OSes.

### 2.3 Windows ClearType anti-aliasing

Body text on Windows can look "harsh" compared to macOS. Mitigate with:

```css
body {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
}
```

### 2.4 Battery saver / power throttling

Windows in battery-saver mode throttles `requestAnimationFrame` to 30fps and disables some effects. Your animations will look slower but should still work.

Don't try to detect this — just make animations that work at 30fps too. Test by Chrome DevTools → Performance → CPU 4× slowdown.

### 2.5 Edge blocks some autoplay

Microsoft Edge blocks autoplay of videos with audio or videos in certain contexts. **Always**:

```html
<video autoplay muted loop playsinline preload="metadata">
```

`muted` is mandatory. `playsinline` for iOS / Android. `preload="metadata"` saves bandwidth.

If autoplay is blocked, fall back to a poster image:

```html
<video poster="hero-poster.webp" autoplay muted loop playsinline>
  <source src="hero.mp4" type="video/mp4">
</video>
```

### 2.6 Cleartype and font weight 300

Variable fonts at weight 300 can look **thin and broken** on some Windows + Edge configurations (especially older builds). The hero italic at wght 300 SOFT 100 (Fraunces) may render with anti-aliasing artifacts.

**Solution:** if your hero uses very thin weights, also test at 350 and 400. Pick the lowest that renders cleanly. If 300 is your design choice, accept that some Windows users will see slightly thicker.

### 2.7 GPU acceleration disabled

Some Windows Pro installs (RDP sessions, virtual machines, integrated graphics + bad drivers) have GPU acceleration disabled. This affects:

- WebGL / Three.js — can fall back to software rendering (slow) or fail.
- CSS `filter: blur(70px)` — slow to render.
- `backdrop-filter: blur(20px)` — slow.

**Solution:** for `filter: blur`, lower values when possible. For Three.js, detect and gracefully degrade:

```js
function hasWebGL() {
  try {
    const canvas = document.createElement("canvas");
    return !!(window.WebGLRenderingContext &&
              (canvas.getContext("webgl") || canvas.getContext("experimental-webgl")));
  } catch (e) { return false; }
}

if (!hasWebGL()) {
  // Use a static image or 2D canvas fallback
  document.querySelector(".hero-3d").style.backgroundImage = "url('assets/img/hero-fallback.webp')";
}
```

### 2.8 Old Edge (pre-Chromium) — only if user explicitly says so

EdgeHTML (pre-2020) is dead but some enterprises still have it. If user mentions "old Edge", use only basic CSS, no `backdrop-filter`, no `mix-blend-mode`, no `clip-path`. Default: assume modern Chromium-based Edge (post-2020).

---

## 3. macOS quirks

Less troublesome, but worth noting:

### 3.1 Safari's `100vh` behavior

Safari counts the URL bar in `100vh`, then jumps when it disappears.

**Solution:**

```css
.hero {
  min-height: 100vh;   /* fallback */
  min-height: 100svh;  /* small viewport — always-visible area */
}
```

### 3.2 Safari and `backdrop-filter`

Older Safari needs `-webkit-backdrop-filter`:

```css
.glass-card {
  background: rgba(255,255,255,0.7);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}
```

### 3.3 Safari `position: fixed` + overflow

Bug in older Safari where fixed elements jump on scroll. Mitigate with `transform: translateZ(0)` on the fixed element to force its own compositor layer.

---

## 4. Mobile / iOS quirks

### 4.1 iOS `touch-action`

For carousels with horizontal scroll, ensure:

```css
.carousel { touch-action: pan-x; }
```

### 4.2 iOS Safari clamp viewport

```css
html { -webkit-text-size-adjust: 100%; }
```

### 4.3 Hover on touch devices

Touch devices "fake" hover by sticking after tap. Always pair `:hover` with feature query:

```css
@media (hover: hover) {
  .card:hover { /* ... */ }
}
```

Or check in JS:

```js
if (matchMedia("(hover: none)").matches) return;
```

### 4.4 iOS keyboard pushes layout

When a form input is focused on iOS, the keyboard pushes the page up. Position-fixed elements behave weirdly.

**Solution:** test forms on iOS simulator. If buttons / labels become hidden, add `padding-bottom` to the form on focus.

### 4.5 Three.js on mobile

```js
const isMobile = window.innerWidth < 900 || /Mobi|Android/i.test(navigator.userAgent);
renderer.setPixelRatio(Math.min(devicePixelRatio || 1, isMobile ? 1.5 : 2));
if (isMobile) {
  renderer.shadowMap.enabled = false;        // ⚠️ shadows off on mobile
  renderer.antialias = false;
}
```

---

## 5. Browser feature detection patterns

Always feature-detect, never user-agent-sniff:

```js
// ✅ CORRECT
if (CSS.supports("backdrop-filter", "blur(10px)")) { /* ... */ }
if (typeof IntersectionObserver !== "undefined") { /* ... */ }
if (matchMedia("(hover: hover)").matches) { /* ... */ }
if ("startViewTransition" in document) { /* ... */ }

// ❌ AVOID
if (navigator.userAgent.includes("Edge")) { /* ... */ }
```

---

## 6. Common error messages and fixes

| User reports | Likely cause | Fix |
|---|---|---|
| "Nothing moves on Windows" | reduced-motion gating too aggressive | See §1 |
| "I see a black square in the corner at startup" | Cursor before first mousemove | Gotcha A.3 |
| "The site looks fine on phone but broken on iPad" | Breakpoint missing for tablet | Add 720px / 960px breakpoints |
| "Some images don't load" | Mixed format references | Gotcha A.10, run grep |
| "The menu won't appear" | Module imports in file:// | Gotcha A.1 |
| "Spinner is stuck" | Splash JS failed | Gotcha A.9 (CSS safety net) |
| "Page looks washed out on my laptop" | High brightness + low contrast settings + low-contrast palette | Make sure body text contrast >= 7:1 against bg |
| "Animation choppy on my old laptop" | GPU acceleration off / battery save | Reduce particle count, blur values, use `will-change` only on actively animating elements |
| "Cards don't tilt on my Surface" | hover detected as `none` (touch screen) | Use `(hover: hover) and (pointer: fine)` or just `(hover: hover)` depending on need |
| "Form keeps re-submitting" | No `preventDefault()` or no disable while submitting | Gotcha 12.1 in catalog |

---

## 7. The 3-machine smoke test

Before declaring a project done, simulate three user environments:

### Test 1 — Windows reduced-motion

DevTools → Rendering → Emulate `prefers-reduced-motion: reduce`. Reload.
- ✅ Hover effects work.
- ✅ Scroll is shorter but smooth.
- ✅ Cards tilt.
- ✅ Reveals appear (faster, but appear).
- ✅ Marquee moves.

If any of these fail, you're gating too aggressively.

### Test 2 — Mobile / touch

DevTools → Toggle device toolbar → iPhone 12 Pro.
- ✅ All content readable.
- ✅ No horizontal overflow.
- ✅ Mobile nav (hamburger) works.
- ✅ Forms submittable.
- ✅ Lazy images load.
- ✅ No hover-only interactions block content.

### Test 3 — JavaScript disabled

DevTools → Settings → Disable JavaScript. Reload.
- ✅ All content visible (heroes, products, contact info).
- ✅ Navigation works (anchors).
- ✅ Forms can be filled (won't submit dynamically, but inputs work).
- ✅ Layout intact, just without animations.

If any text is missing or layout broken without JS, you're hardcoding too little in HTML.

---

## 8. Hostinger-specific notes

The user will deploy to Hostinger via FTP / File Manager. A few notes:

- Hostinger serves `.webp` correctly with the right MIME type out of the box.
- `.html` files at the root level work as expected.
- Subdirectories like `/lib/` and `/assets/` work without any config.
- `index.html` is auto-served at root.
- For multi-page sites, `/about.html`, `/contact.html` etc. work as `yourdomain.com/about` and `yourdomain.com/contact` if Hostinger has "Pretty URLs" enabled. Otherwise, use full `.html` extension in links.

**Test before declaring deploy-ready:**
- Open `index.html` directly via `file://` (double-click). Should work.
- Run `python -m http.server 8000` from the project folder, open `http://localhost:8000`. Should work identically.

If both pass, Hostinger upload will work too.

---

## 9. The "non-technical user opens the file" stress test

Simulate the exact end-user experience:

1. Take the project folder.
2. Zip it.
3. Unzip it on a different machine.
4. Open `index.html` by **double-clicking** (no terminal, no localhost).
5. Verify the entire site renders with all content and animations.

If you see CORS errors, broken content, broken animations → you've used something that requires HTTP origin (modules with imports, fetch with relative paths in some cases). Fix and retest.

---

## 10. Final checklist for cross-platform robustness

- [ ] No `<script type="module">` with relative imports.
- [ ] No `import` / `export` keywords in any deliverable JS.
- [ ] `prefers-reduced-motion` only gates intrusive effects (autoplay video, particles, big parallax, infinite loops).
- [ ] `prefers-reduced-motion` does NOT disable: tilt, hover, fade, mesh, count-up, color transition, scramble, marquee, smooth scroll (just shortens it).
- [ ] DPR capped at 2 for canvas / Three.js.
- [ ] All `<video>` have `muted playsinline`.
- [ ] WebGL feature-detected with fallback.
- [ ] `backdrop-filter` has a solid background fallback.
- [ ] `100svh` used for full-viewport heroes.
- [ ] `(hover: hover)` gating for hover-only interactions.
- [ ] Site renders fully on `file://` open.
- [ ] Site renders fully with JS disabled (just static).
- [ ] Tested in Chrome, Firefox, Safari, Edge (or at least Chromium + Safari + Firefox via responsive device mode).
- [ ] Cursor doesn't appear in (0,0) at load.

If all checked, the website behaves consistently across the realistic spectrum of end-user setups.
