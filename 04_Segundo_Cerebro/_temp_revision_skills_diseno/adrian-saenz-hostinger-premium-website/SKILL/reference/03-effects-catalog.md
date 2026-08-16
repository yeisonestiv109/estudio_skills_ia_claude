# Effects Catalog

Copy-paste-ready snippets for every effect used in modern premium webs (2026 vintage). Organized by category. Each effect has:
- Where it works (which archetypes use it).
- Snippet (HTML / CSS / JS as needed).
- Critical gotchas inline.

**Rule:** pick **4–5 effects** for any given project. NEVER 12. A web with 12 effects looks like a showcase, not a product.

---

## Index

1. Cursor & pointer
2. Scroll-driven
3. Page transitions
4. WebGL / Canvas / Shaders
5. Image effects
6. Typography effects
7. Micro-interactions
8. Premium navigation
9. Layout & composition
10. Color & light
11. Storytelling
12. Forms & feedback

---

# 1. Cursor & pointer

### 1.1 Custom cursor — two clean circles

**Used in:** archetypes 01, 02, 05, 07.
**Skip in:** 06 (Newspaper), 09 (Magazine multi-page) — content-first.

```html
<div class="cursor" data-cursor-root>
  <span class="cursor-dot"></span>
  <span class="cursor-ring"></span>
</div>
```

```css
.cursor {
  position: fixed; top: 0; left: 0;
  pointer-events: none; z-index: 9999;
  display: none;
  mix-blend-mode: difference;
  opacity: 0;             /* HIDE until first mousemove (no 0,0 flash) */
  transition: opacity .25s var(--ease-out);
}
.cursor.is-ready { opacity: 1; }
@media (hover: hover) and (pointer: fine) { .cursor { display: block; } }
.cursor-dot, .cursor-ring {
  position: fixed; top: 0; left: 0; pointer-events: none; will-change: transform;
}
.cursor-dot { width: 5px; height: 5px; margin: -2.5px; background: var(--cream); border-radius: 50%; }
.cursor-ring {
  width: 32px; height: 32px; margin: -16px; border: 1px solid var(--cream); border-radius: 50%;
  transition: width .35s var(--ease-out), height .35s var(--ease-out), margin .35s var(--ease-out);
}
.cursor.is-interactive .cursor-ring { width: 48px; height: 48px; margin: -24px; }
.has-cursor, .has-cursor a, .has-cursor button { cursor: none; }
```

```js
function initCursor() {
  const root = document.querySelector("[data-cursor-root]");
  if (!root || !matchMedia("(hover: hover) and (pointer: fine)").matches) return;
  document.documentElement.classList.add("has-cursor");
  const ring = root.querySelector(".cursor-ring");
  const dot = root.querySelector(".cursor-dot");
  let tx = 0, ty = 0, rx = 0, ry = 0, firstMove = false;

  window.addEventListener("mousemove", (e) => {
    tx = e.clientX; ty = e.clientY;
    if (dot) dot.style.transform = `translate3d(${tx}px, ${ty}px, 0)`;
    if (!firstMove) {
      firstMove = true;
      rx = tx; ry = ty;
      if (ring) ring.style.transform = `translate3d(${rx}px, ${ry}px, 0)`;
      root.classList.add("is-ready");
    }
  }, { passive: true });

  function tick() {
    rx += (tx - rx) * 0.18; ry += (ty - ry) * 0.18;
    if (ring) ring.style.transform = `translate3d(${rx}px, ${ry}px, 0)`;
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);

  const HOVERABLES = "[data-cursor], .card, .btn, a[href]";
  document.addEventListener("mouseover", e => { if (e.target.closest(HOVERABLES)) root.classList.add("is-interactive"); });
  document.addEventListener("mouseout",  e => {
    if (e.target.closest(HOVERABLES) && !e.relatedTarget?.closest?.(HOVERABLES))
      root.classList.remove("is-interactive");
  });
}
```

**Gotchas:**
- ⚠️ NEVER text inside the cursor ("Ver", "Discover"). Discontinued anti-pattern.
- ⚠️ NEVER spotlight cursor (light circle that obscures rest). Pop-quirky, blocks reading.
- ⚠️ The `opacity: 0` until `.is-ready` is mandatory or you get a black mark in (0,0) at load.

### 1.2 Magnetic buttons

**Used in:** archetypes 01, 04. Skip in 06, 09, 07.
**Never on form submit buttons.** They cause UX disasters.

```html
<a class="btn-magnetic" data-magnetic data-magnetic-strength="0.3">Action</a>
```

```css
.has-magnetic { display: inline-flex; position: relative; isolation: isolate; }
.magnetic-inner {
  display: inline-flex; align-items: center; justify-content: center; gap: inherit;
  will-change: transform;
  transition: transform .8s var(--ease-soft);
}
```

```js
function initMagnetic() {
  if (!matchMedia("(hover: hover) and (pointer: fine)").matches) return;
  document.querySelectorAll("[data-magnetic]").forEach(el => {
    const strength = parseFloat(el.dataset.magneticStrength || "0.3");
    const inner = document.createElement("span");
    inner.className = "magnetic-inner";
    while (el.firstChild) inner.appendChild(el.firstChild);
    el.appendChild(inner);
    el.classList.add("has-magnetic");
    let tx=0, ty=0, cx=0, cy=0, raf=null;
    el.addEventListener("mousemove", e => {
      const r = el.getBoundingClientRect();
      tx = ((e.clientX - r.left) - r.width/2) * strength;
      ty = ((e.clientY - r.top) - r.height/2) * strength;
      if (!raf) raf = requestAnimationFrame(loop);
    });
    el.addEventListener("mouseleave", () => { tx=0; ty=0; if (!raf) raf = requestAnimationFrame(loop); });
    function loop() {
      cx += (tx - cx) * 0.2; cy += (ty - cy) * 0.2;
      inner.style.transform = `translate3d(${cx}px, ${cy}px, 0)`;
      raf = (Math.abs(tx-cx)>0.1 || Math.abs(ty-cy)>0.1) ? requestAnimationFrame(loop) : null;
    }
  });
}
```

### 1.3 Cursor with monospace coordinates (Brutalist 07)

```html
<div class="cursor-coord" data-cursor-coord></div>
```
```css
.cursor-coord {
  position: fixed; pointer-events: none; z-index: 9999;
  font-family: var(--mono);
  font-size: 11px; color: var(--ink);
  background: var(--bg);
  padding: 2px 6px; border: 1px solid var(--ink);
  transform: translate(20px, 20px);
  opacity: 0; transition: opacity .2s;
}
```
```js
const coord = document.querySelector("[data-cursor-coord]");
window.addEventListener("mousemove", e => {
  coord.style.left = e.clientX + "px";
  coord.style.top = e.clientY + "px";
  coord.textContent = `[${e.clientX}, ${e.clientY}]`;
  coord.style.opacity = 1;
});
```

### 1.4 Mouse-reactive gradient (Archetype 05)

See section 4.5 below.

---

# 2. Scroll-driven

### 2.1 Lenis smooth scroll

**Used everywhere except 06 (Newspaper) and 09 — content-first reading.**

```js
function initLenis() {
  if (!window.Lenis) return;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const lenis = new window.Lenis({
    duration: reduced ? 0.7 : 1.15,    // reduced ≠ off, just shorter
    easing: t => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
    smoothWheel: true, smoothTouch: false,
  });
  window.lenis = lenis;
  function raf(time) { lenis.raf(time); requestAnimationFrame(raf); }
  requestAnimationFrame(raf);
  if (window.gsap && window.ScrollTrigger) {
    lenis.on("scroll", ScrollTrigger.update);
    gsap.ticker.add(time => lenis.raf(time * 1000));
    gsap.ticker.lagSmoothing(0);
  }
}

// Anchors
function initSmoothAnchors() {
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
}
```

### 2.2 ScrollTrigger pinned horizontal showcase (Archetype 02)

```js
function initShowcasePinned() {
  if (!window.gsap || !window.ScrollTrigger) return;
  const sec = document.querySelector(".showcase");
  const track = document.querySelector("[data-showcase]");
  if (!sec || !track) return;

  const setup = () => {
    ScrollTrigger.getAll().forEach(s => { if (s.vars.id === "showcase-pin") s.kill(); });
    const isDesktop = window.innerWidth >= 1024;
    sec.classList.toggle("is-pinned", isDesktop);
    if (!isDesktop) return;
    const trackRect = track.getBoundingClientRect();
    const distance = track.scrollWidth - window.innerWidth + trackRect.left + 16;
    if (distance <= 0) return;

    gsap.to(track, {
      x: () => -distance, ease: "none",
      scrollTrigger: {
        id: "showcase-pin",
        trigger: sec, start: "top top+=72",
        end: () => "+=" + (distance + window.innerHeight * 0.4),
        pin: true, scrub: 0.6, invalidateOnRefresh: true, anticipatePin: 1,
      }
    });
    // ⚠️ DO NOT add gsap.from on the children inside pinned section. They'll stay translucent.
  };

  setup();
  let to;
  window.addEventListener("resize", () => { clearTimeout(to); to = setTimeout(() => { ScrollTrigger.refresh(); setup(); }, 250); });
}
```

### 2.3 Scroll progress bar (top of viewport)

```html
<div class="scroll-progress" aria-hidden="true"><span data-scroll-progress></span></div>
```
```css
.scroll-progress {
  position: fixed; top: 0; left: 0; right: 0; height: 2px;
  z-index: 200; background: rgba(0,0,0,0.06); pointer-events: none;
}
.scroll-progress span {
  display: block; height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--accent-2));
  transform-origin: 0 0; transform: scaleX(0); transition: transform .08s linear;
}
```
```js
function initScrollProgress() {
  const bar = document.querySelector("[data-scroll-progress]");
  if (!bar) return;
  let raf=null;
  function update() {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    const pct = max > 0 ? scrollY / max : 0;
    bar.style.transform = `scaleX(${pct})`;
    raf = null;
  }
  window.addEventListener("scroll", () => { if (!raf) raf = requestAnimationFrame(update); }, { passive: true });
  update();
}
```

### 2.4 Reveal on scroll (universal)

```html
<div data-reveal>Content</div>
```
```css
[data-reveal] {
  opacity: 0; transform: translateY(40px);
  transition: opacity .8s var(--ease-soft), transform .8s var(--ease-soft);
}
[data-reveal].is-revealed { opacity: 1; transform: none; }
```
```js
function initReveals() {
  const els = document.querySelectorAll("[data-reveal]");
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add("is-revealed");
        io.unobserve(e.target);
      }
    });
  }, {
    threshold: 0.01,                    // VERY low — large images would never reach 0.18
    rootMargin: "0px 0px -2% 0px",
  });
  els.forEach(el => io.observe(el));

  // ⚠️ SAFETY NET: at 6s, reveal anything still hidden above the fold
  setTimeout(() => {
    document.querySelectorAll("[data-reveal]:not(.is-revealed)").forEach(el => {
      if (el.getBoundingClientRect().top < window.innerHeight) {
        el.classList.add("is-revealed");
      }
    });
  }, 6000);
}
```

### 2.5 Hero parallax (multilayer)

```js
function initHeroParallax() {
  if (!window.gsap || !window.ScrollTrigger) return;
  const heroBg = document.querySelector(".hero-bg");
  const heroContent = document.querySelector(".hero-content");
  if (heroBg) {
    gsap.to(heroBg, {
      yPercent: 30, scale: 1.15, ease: "none",
      scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: true }
    });
  }
  if (heroContent) {
    gsap.to(heroContent, {
      yPercent: -55, opacity: 0, ease: "none",
      scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: true }
    });
  }
}
```

### 2.6 Native CSS scroll-driven (modern browsers)

For Chrome/Edge 115+ and Safari 18.4+:

```css
@supports (animation-timeline: scroll()) {
  .hero-title {
    animation: heroFadeOut linear;
    animation-timeline: scroll();
    animation-range: 0 30vh;
  }
  @keyframes heroFadeOut {
    to { opacity: 0; transform: translateY(-30px); }
  }
}
```

No JS needed. Falls back gracefully to no animation in older browsers.

### 2.7 Scroll-snap fullscreen (Archetype 03 alternative)

```css
html { scroll-snap-type: y mandatory; scroll-behavior: smooth; }
section { scroll-snap-align: start; min-height: 100svh; }
```

⚠️ Don't combine with Lenis — they fight each other.

### 2.8 Image sequence scroll (Apple AirPods style)

For demanding projects:
```js
const frames = []; // pre-loaded array of Image objects
let currentFrame = 0;
window.addEventListener("scroll", () => {
  const max = document.documentElement.scrollHeight - innerHeight;
  const pct = scrollY / max;
  const frameIdx = Math.floor(pct * (frames.length - 1));
  if (frameIdx !== currentFrame) {
    currentFrame = frameIdx;
    canvas.getContext("2d").drawImage(frames[frameIdx], 0, 0, canvas.width, canvas.height);
  }
});
```

⚠️ Only use if you have a real image sequence (~60 frames). Heavy on initial load.

---

# 3. Page transitions

### 3.1 View Transitions API (zero-JS)

```css
@view-transition { navigation: auto; }
::view-transition-old(root),
::view-transition-new(root) {
  animation-duration: 0.6s; animation-timing-function: cubic-bezier(0.16, 1, 0.3, 1);
}
::view-transition-old(root) { animation-name: fadeOutUp; }
::view-transition-new(root) { animation-name: fadeInUp; }
@keyframes fadeOutUp { to { opacity: 0; transform: translateY(-12px); } }
@keyframes fadeInUp  { from { opacity: 0; transform: translateY(12px); } }
```

### 3.2 Curtain wipe transition

```css
.curtain {
  position: fixed; inset: 0; z-index: 9999;
  background: var(--ink);
  transform: translateY(100%);
  transition: transform .8s var(--ease-soft);
  pointer-events: none;
}
.curtain.is-out { transform: translateY(0); }
.curtain.is-in  { transform: translateY(-100%); transition-delay: .1s; }
```

### 3.3 Splash loader with double safety

```html
<div class="splash" data-splash aria-hidden="true">
  <div class="splash-inner">
    <img src="assets/img/logo.webp" alt="" class="splash-logo" />
    <span class="splash-line"></span>
  </div>
</div>
```
```css
.splash {
  position: fixed; inset: 0; z-index: 10000;
  background: var(--bg);
  display: grid; place-items: center;
  pointer-events: auto;
  transition: opacity .9s, clip-path 1.1s;
  /* ⚠️ MANDATORY safety net via CSS animation in case JS fails */
  animation: splashSafety .01s 4.5s forwards;
}
.splash.is-out {
  opacity: 0; pointer-events: none;
  clip-path: inset(0 0 100% 0);
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
  setTimeout(hide, 4000); // additional safety
}
```

---

# 4. WebGL / Canvas / Shaders

### 4.1 Three.js setup (Archetype 03)

```js
// three-setup.js — assumes <script src="lib/three.min.js"></script> already loaded
window.TG = (function () {
  const isMobile = window.innerWidth < 900;
  const renderer = new THREE.WebGLRenderer({
    antialias: !isMobile, alpha: true, powerPreference: "high-performance",
  });
  renderer.setPixelRatio(Math.min(devicePixelRatio, isMobile ? 1.5 : 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.78;             // ⚠️ Calibrated value
  renderer.outputEncoding = THREE.sRGBEncoding;
  if (!isMobile) {
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  }
  document.querySelector("[data-canvas]").appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x080604, 0.032); // ⚠️ Calibrated value

  const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 200);
  camera.position.set(0, 6, 12);

  // 4-light cinematic setup
  scene.add(new THREE.AmbientLight(0x2a1d10, 0.42));
  const key = new THREE.DirectionalLight(0xffd88c, 1.18);
  key.position.set(10, 18, 8); key.castShadow = !isMobile;
  if (!isMobile) {
    key.shadow.mapSize.set(2048, 2048);
    Object.assign(key.shadow.camera, { left: -20, right: 20, top: 20, bottom: -20 });
    key.shadow.bias = -0.0005;
  }
  scene.add(key);
  scene.add(new THREE.DirectionalLight(0x8ab0ff, 0.28).position.set(-8, 6, -5));
  const accent = new THREE.PointLight(0xc9a961, 0.75, 30);
  accent.position.set(0, 4, 6); scene.add(accent);

  const updaters = [];
  function start() {
    function loop(t) {
      updaters.forEach(fn => fn(t));
      renderer.render(scene, camera);
      requestAnimationFrame(loop);
    }
    requestAnimationFrame(loop);
  }
  window.addEventListener("resize", () => {
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
  });
  renderer.setSize(innerWidth, innerHeight);
  return { renderer, scene, camera, isMobile, addUpdater: fn => updaters.push(fn), start };
})();
```

### 4.2 Procedural canvas texture (no GLTF needed)

```js
function makeWoodTexture(baseColor) {
  const c = document.createElement("canvas"); c.width = c.height = 256;
  const ctx = c.getContext("2d");
  ctx.fillStyle = baseColor; ctx.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 50; i++) {
    ctx.strokeStyle = `rgba(0,0,0,${0.05 + Math.random()*0.12})`;
    ctx.lineWidth = 1 + Math.random() * 2;
    ctx.beginPath();
    ctx.moveTo(0, Math.random() * 256);
    ctx.bezierCurveTo(64, Math.random()*256, 192, Math.random()*256, 256, Math.random()*256);
    ctx.stroke();
  }
  return new THREE.CanvasTexture(c);
}
```

### 4.3 Mesh gradient animado (CSS, no WebGL)

The "3D moving background" effect from Restaurante 911. Cheap, beautiful.

```css
@property --mesh-angle { syntax: "<angle>"; inherits: false; initial-value: 0deg; }
@property --mesh-x     { syntax: "<percentage>"; inherits: false; initial-value: 50%; }
@property --mesh-y     { syntax: "<percentage>"; inherits: false; initial-value: 50%; }

.section-with-mesh {
  position: relative; overflow: hidden; isolation: isolate;
}
.section-with-mesh::before {
  content: ""; position: absolute; inset: -10%; z-index: -1;
  background:
    radial-gradient(60% 50% at var(--mesh-x) var(--mesh-y),
      rgba(197,48,30,.35), transparent 60%),
    conic-gradient(from var(--mesh-angle),
      rgba(196,154,91,.2), rgba(122,145,89,.08), rgba(197,48,30,.2), rgba(196,154,91,.2));
  filter: blur(80px) saturate(120%);
  opacity: .7;
  animation: meshShift 22s linear infinite;
  mix-blend-mode: screen;
}
@keyframes meshShift {
  0%   { --mesh-angle: 0deg;   --mesh-x: 30%; --mesh-y: 40%; }
  50%  { --mesh-angle: 180deg; --mesh-x: 70%; --mesh-y: 60%; }
  100% { --mesh-angle: 360deg; --mesh-x: 30%; --mesh-y: 40%; }
}
```

### 4.4 Particle dust system (canvas 2D, lightweight)

```js
function initParticles() {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced) return;       // ⚠️ Particles ARE intrusive — gate by reduced-motion
  const canvas = document.createElement("canvas");
  canvas.className = "particles";
  document.body.appendChild(canvas);
  const ctx = canvas.getContext("2d");
  const dpr = Math.min(devicePixelRatio || 1, 1.5);
  const particles = [];
  const COUNT = 80;

  function resize() {
    canvas.width = innerWidth * dpr;
    canvas.height = innerHeight * dpr;
    canvas.style.cssText = `position:fixed;inset:0;pointer-events:none;z-index:1;mix-blend-mode:screen;`;
    ctx.scale(dpr, dpr);
  }
  resize(); window.addEventListener("resize", () => { ctx.setTransform(1,0,0,1,0,0); resize(); });

  for (let i = 0; i < COUNT; i++) {
    particles.push({
      x: Math.random() * innerWidth, y: Math.random() * innerHeight,
      r: 0.4 + Math.random() * 1.8,
      vx: (Math.random() - 0.5) * 0.15,
      vy: -0.05 - Math.random() * 0.25,
      a: 0.15 + Math.random() * 0.5,
    });
  }

  function frame() {
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    for (const p of particles) {
      p.x += p.vx; p.y += p.vy;
      if (p.y < -10) { p.y = innerHeight + 10; p.x = Math.random() * innerWidth; }
      ctx.fillStyle = `rgba(255,255,255,${p.a})`;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI*2); ctx.fill();
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}
```

### 4.5 Mouse-reactive radial gradient mesh (Archetype 05)

```css
.hero-gradient {
  position: absolute; inset: 0; z-index: -1;
  background:
    radial-gradient(circle 600px at var(--mx, 50%) var(--my, 50%),
      var(--gradient-1) 0%, transparent 50%),
    radial-gradient(circle 800px at calc(var(--mx, 50%) + 10%) calc(var(--my, 50%) - 10%),
      var(--gradient-2) 0%, transparent 50%),
    radial-gradient(circle 700px at calc(var(--mx, 50%) - 15%) calc(var(--my, 50%) + 15%),
      var(--gradient-3) 0%, transparent 50%),
    var(--bg);
  filter: blur(40px) saturate(150%);
}
```
```js
let mx = 50, my = 50;
let tx = 50, ty = 50;
document.addEventListener("mousemove", e => {
  tx = (e.clientX / innerWidth) * 100;
  ty = (e.clientY / innerHeight) * 100;
});
function gradFrame() {
  mx += (tx - mx) * 0.06;
  my += (ty - my) * 0.06;
  document.documentElement.style.setProperty("--mx", mx + "%");
  document.documentElement.style.setProperty("--my", my + "%");
  requestAnimationFrame(gradFrame);
}
requestAnimationFrame(gradFrame);
```

### 4.6 ⚠️ Avoid WebGL displacement on hero photos

This was tried in Nómada and removed. WebGL displacement on hero images:
- Can flip the image (UV/UNPACK_FLIP_Y mismatch).
- Looks "gimmicky" in editorial contexts.
- Better alternatives: parallax + ambient zoom + chromatic hover.

**Skip unless the user explicitly asks for psychedelic/distorted backgrounds.**

---

# 5. Image effects

### 5.1 Tilt 3D subtle (max 7–9°)

```css
.has-tilt {
  --rx: 0deg; --ry: 0deg;
  transform: perspective(900px) rotateX(var(--rx)) rotateY(var(--ry));
  transform-style: preserve-3d;
  transition: transform .55s var(--ease-soft);
}
.has-tilt:hover { transition-duration: .15s; }
.has-tilt .card-meta { transform: translateZ(40px); }
```
```js
function initTilt() {
  if (matchMedia("(hover: none)").matches) return;
  document.querySelectorAll(".card, .exp-card").forEach(card => {
    const MAX = 7;
    let tx=0, ty=0, cx=0, cy=0, raf=null;
    card.classList.add("has-tilt");
    card.addEventListener("mousemove", e => {
      const r = card.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width  - 0.5;
      const py = (e.clientY - r.top)  / r.height - 0.5;
      tx = -py * MAX; ty = px * MAX;
      if (!raf) raf = requestAnimationFrame(loop);
    });
    card.addEventListener("mouseleave", () => { tx=0; ty=0; if (!raf) raf = requestAnimationFrame(loop); });
    function loop() {
      cx += (tx - cx) * 0.15; cy += (ty - cy) * 0.15;
      card.style.setProperty("--rx", cx.toFixed(2) + "deg");
      card.style.setProperty("--ry", cy.toFixed(2) + "deg");
      raf = (Math.abs(tx-cx)>0.05 || Math.abs(ty-cy)>0.05) ? requestAnimationFrame(loop) : null;
    }
  });
}
```

### 5.2 Hover image: scale + saturate + chromatic aberration

```css
.card .card-img { transition: transform .8s var(--ease-soft), filter .55s; }
.card:hover .card-img {
  transform: scale(1.12);
  filter: saturate(1.18) brightness(1.05) contrast(1.05)
          drop-shadow(4px 0 0 rgba(184,92,58,0.5))
          drop-shadow(-4px 0 0 rgba(74,93,58,0.4));
}
.card:hover {
  box-shadow:
    0 50px 100px -20px rgba(184,92,58,0.35),
    0 30px 60px -15px rgba(26,26,26,0.4),
    0 0 0 1px rgba(184,92,58,0.25);
}
```

### 5.3 Ken Burns ambient zoom

```css
@keyframes ambientZoom {
  0%, 100% { transform: scale(1.05) translate3d(0, 0, 0); }
  50%      { transform: scale(1.12) translate3d(-1%, -1%, 0); }
}
.hero-bg img.ambient-on { animation: ambientZoom 28s ease-in-out infinite; }
```

### 5.4 Clip-path reveal (image enters from a shape)

```css
[data-reveal-mask] {
  clip-path: inset(0 0 100% 0);
  transition: clip-path 1.1s var(--ease-soft);
}
[data-reveal-mask].is-revealed {
  clip-path: inset(0);
}
```

### 5.5 Grain SVG overlay

```css
.has-grain { position: relative; }
.has-grain::after {
  content: ""; position: absolute; inset: 0;
  pointer-events: none; opacity: 0.18; mix-blend-mode: overlay;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0.5 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>");
  background-size: 220px 220px;
}
```

### 5.6 Duotone with animated gradient

```css
.duotone {
  position: relative; overflow: hidden;
}
.duotone img {
  filter: grayscale(1) contrast(1.1);
  mix-blend-mode: luminosity;
}
.duotone::before {
  content: ""; position: absolute; inset: 0;
  background: linear-gradient(135deg, var(--accent-1), var(--accent-2));
  mix-blend-mode: multiply;
}
```

---

# 6. Typography effects

### 6.1 Split text reveals (chars / words / lines)

```html
<h1 data-split="chars">Title</h1>
<p data-split="words">Long text…</p>
<p data-split="lines">Very long text…</p>
```

```js
function splitChars(el) {
  el.setAttribute("aria-label", el.textContent.trim());
  const html = Array.from(el.childNodes).map(node => {
    if (node.nodeType === 3) {
      return [...node.textContent].map(ch =>
        ch === " " ? " " : `<span class="split-char" aria-hidden="true">${escHTML(ch)}</span>`
      ).join("");
    }
    if (node.nodeName === "BR") return "<br>";
    if (node.nodeType === 1) {
      const tag = node.tagName.toLowerCase();
      const inner = [...node.textContent].map(ch =>
        ch === " " ? " " : `<span class="split-char" aria-hidden="true">${escHTML(ch)}</span>`
      ).join("");
      return `<${tag}>${inner}</${tag}>`;
    }
    return "";
  }).join("");
  el.innerHTML = html;
  return el.querySelectorAll(".split-char");
}

function splitWords(el) {
  // ⚠️ MUST iterate childNodes to preserve <br> and <em>!
  el.setAttribute("aria-label", el.textContent.trim().replace(/\s+/g, " "));
  const wrapWords = text => text.split(/(\s+)/).map(w =>
    /^\s+$/.test(w) ? w : `<span class="split-word" aria-hidden="true">${escHTML(w)}</span>`
  ).join("");
  const html = Array.from(el.childNodes).map(node => {
    if (node.nodeType === 3) return wrapWords(node.textContent);
    if (node.nodeName === "BR") return "<br>";
    if (node.nodeType === 1) {
      const tag = node.tagName.toLowerCase();
      return `<${tag}>${wrapWords(node.textContent)}</${tag}>`;
    }
    return "";
  }).join("");
  el.innerHTML = html;
  return el.querySelectorAll(".split-word");
}

function initSplitText() {
  if (!window.gsap || !window.ScrollTrigger) return;
  document.querySelectorAll("[data-split]").forEach(el => {
    const mode = el.dataset.split;
    const parts = mode === "chars" ? splitChars(el) : splitWords(el);
    gsap.set(parts, { y: 24, opacity: 0 });
    gsap.to(parts, {
      y: 0, opacity: 1,
      duration: mode === "chars" ? 0.7 : 0.9,
      stagger: mode === "chars" ? 0.018 : 0.04,
      ease: "expo.out",
      scrollTrigger: { trigger: el, start: "top 88%", once: true },
    });
  });
}
```

### 6.2 Variable font breathing (subtle weight pulse)

```css
@property --breathe-wght { syntax: "<number>"; inherits: false; initial-value: 300; }
[data-breathe] {
  --breathe-wght: 300;
  font-variation-settings: "wght" var(--breathe-wght), "opsz" 144;
}
```
```js
gsap.to("[data-breathe]", {
  "--breathe-wght": 480,
  duration: 4.5, ease: "sine.inOut", yoyo: true, repeat: -1,
});
```

### 6.3 Marquee infinite ticker

```html
<div class="marquee">
  <div class="marquee-track" data-marquee>
    <span>Item</span><span>·</span><span>Item</span><span>·</span><!-- ... -->
  </div>
</div>
```
```css
.marquee { overflow: hidden; position: relative; }
.marquee::before, .marquee::after {
  content: ""; position: absolute; top: 0; bottom: 0; width: 80px; z-index: 2; pointer-events: none;
}
.marquee::before { left: 0;  background: linear-gradient(90deg, var(--bg), transparent); }
.marquee::after  { right: 0; background: linear-gradient(270deg, var(--bg), transparent); }
.marquee-track { display: inline-flex; gap: 3rem; white-space: nowrap; will-change: transform; }
```
```js
function initMarquee() {
  if (!window.gsap) return;
  document.querySelectorAll("[data-marquee]").forEach(track => {
    const clone = track.cloneNode(true);
    clone.removeAttribute("data-marquee");
    track.parentNode.appendChild(clone);
    const distance = track.scrollWidth;
    const speed = 60; // px/sec
    gsap.to([track, clone], {
      x: -distance, duration: distance / speed, ease: "none", repeat: -1,
      modifiers: { x: gsap.utils.unitize(x => parseFloat(x) % distance) },
    });
  });
}
```

### 6.4 Letter scramble (single-language)

```js
const GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚáéíóú·@#&%/";

function initScramble() {
  document.querySelectorAll("[data-scramble]").forEach(el => {
    const original = el.textContent;
    let animating = false;
    el.addEventListener("mouseenter", () => {
      if (animating) return;       // ⚠️ Prevent flicker
      animating = true;
      const chars = [...original];
      const delays = chars.map((_, i) => 60 + i * 28 + Math.random() * 80);
      const start = performance.now();
      function tick(now) {
        const elapsed = now - start;
        el.textContent = chars.map((c, i) => {
          if (c === " ") return " ";
          if (elapsed < delays[i]) return GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
          return c;
        }).join("");
        if (chars.some((c, i) => c !== " " && elapsed < delays[i])) {
          requestAnimationFrame(tick);
        } else { el.textContent = original; animating = false; }
      }
      requestAnimationFrame(tick);
    });
    // ⚠️ NO mouseleave handler — let the animation finish naturally
  });
}
```

### 6.5 Bilingual scramble (multi-script)

See Nómada's `lib/bilingual.js`. The `bindBilingual()` function is idempotent and binds listeners per element.

Key principles:
- Use `mouseover/mouseout` with `relatedTarget` check — NOT `mouseenter/mouseleave` (those don't dispatch synthetically in some preview environments).
- Pool of glyphs per script (Latin, Kanji, Arabic, Cyrillic, Georgian, Devanagari, Ethiopic).
- Throttle char swap to ~70ms (rAF would be too fast for the eye).
- Queue mechanism: if user hovers/leaves mid-animation, queue the next intent and execute on completion.
- Mark elements with `data-bilingual-bound` to make idempotent.

### 6.6 Drop cap

```css
.dropcap {
  float: left;
  font-family: var(--serif);
  font-size: 4.6rem; line-height: .85;
  margin: .15rem .55rem -.2rem 0;
  color: var(--accent);
  font-style: italic;
}
```

### 6.7 Animated counter (count-up)

```html
<span data-count-to="4.7">4.7</span>
```
```js
function initCountUp() {
  document.querySelectorAll("[data-count-to]").forEach(el => {
    const target = parseFloat(el.dataset.countTo);
    const decimals = (el.dataset.countTo.split(".")[1] || "").length;
    const obj = { v: 0 };
    const trigger = () => {
      if (window.gsap) {
        gsap.to(obj, { v: target, duration: 1.4, ease: "power2.out",
          onUpdate: () => el.textContent = obj.v.toFixed(decimals) });
      } else {
        el.textContent = target.toFixed(decimals);
      }
    };
    const io = new IntersectionObserver(entries => {
      entries.forEach(e => { if (e.isIntersecting) { trigger(); io.unobserve(e.target); } });
    }, { threshold: 0.5 });
    io.observe(el);
  });
}
```

### 6.8 Outline-on-hover headlines

```css
.headline-outline {
  color: var(--ink);
  -webkit-text-stroke: 1px var(--ink);
  transition: color .4s, -webkit-text-stroke .4s;
}
.headline-outline:hover {
  color: transparent;
  -webkit-text-stroke: 1px var(--accent);
}
```

---

# 7. Micro-interactions

### 7.1 Pop-up button (lift + shadow grow) — preferred for CTAs

```css
.btn {
  box-shadow: 0 4px 14px rgba(0,0,0,0.08), 0 1px 3px rgba(0,0,0,0.06);
  transition: transform .45s var(--ease-soft), box-shadow .45s var(--ease-soft);
}
.btn:hover {
  transform: translateY(-4px);
  box-shadow:
    0 22px 50px rgba(0,0,0,0.18),
    0 10px 22px rgba(184,92,58,0.16);
}
.btn:active {
  transform: translateY(-1px);
  transition-duration: .12s;
}
```

### 7.2 Slide-fill button hover

```css
.btn-slide { position: relative; overflow: hidden; isolation: isolate; }
.btn-slide::before {
  content: ""; position: absolute; inset: 0; z-index: -1;
  background: var(--accent);
  transform: translateX(-101%);
  transition: transform .5s var(--ease-soft);
}
.btn-slide:hover::before { transform: translateX(0); }
```

### 7.3 Animated underline (nav)

```css
.nav-link {
  position: relative;
  padding: 0.25rem 0;
}
.nav-link::after {
  content: ""; position: absolute; left: 0; right: 0; bottom: -3px;
  height: 1px; background: currentColor;
  transform: scaleX(0); transform-origin: right;
  transition: transform .45s var(--ease-soft);
}
.nav-link:hover::after { transform: scaleX(1); transform-origin: left; }
```

### 7.4 Conic gradient border rotating

```css
@property --angle { syntax: "<angle>"; inherits: false; initial-value: 0deg; }
.has-conic-border {
  position: relative; isolation: isolate;
}
.has-conic-border::before {
  content: ""; position: absolute; inset: -2px; z-index: -1;
  border-radius: inherit;
  background: conic-gradient(from var(--angle), var(--accent), transparent, var(--accent));
  animation: rotateConic 4s linear infinite;
}
@keyframes rotateConic { to { --angle: 360deg; } }
```

### 7.5 Confetti on form success

```js
function confettiPop() {
  for (let i = 0; i < 30; i++) {
    const piece = document.createElement("span");
    piece.className = "confetti";
    piece.style.cssText = `
      position: fixed; pointer-events: none; z-index: 9999;
      left: 50%; top: 50%; width: 8px; height: 12px;
      background: hsl(${Math.random()*360}, 80%, 60%);
      transform: translate(-50%, -50%);
      animation: confettiFall ${1+Math.random()}s ease-out forwards;
    `;
    piece.style.setProperty("--tx", `${(Math.random()-0.5)*400}px`);
    piece.style.setProperty("--ty", `${-Math.random()*400}px`);
    piece.style.setProperty("--rot", `${Math.random()*720}deg`);
    document.body.appendChild(piece);
    setTimeout(() => piece.remove(), 1500);
  }
}
```
```css
@keyframes confettiFall {
  to { transform: translate(calc(-50% + var(--tx)), calc(-50% + var(--ty))) rotate(var(--rot)); opacity: 0; }
}
```

---

# 8. Premium navigation

### 8.1 Sticky transparent → solid on scroll

```css
.nav {
  position: fixed; top: 0; inset-inline: 0; z-index: 100;
  transition: background-color .4s var(--ease-out), backdrop-filter .4s var(--ease-out), box-shadow .4s var(--ease-out);
}
.nav.is-scrolled {
  background: rgba(255,255,255,0.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow: 0 1px 0 rgba(0,0,0,0.08);
}
```
```js
function initNav() {
  const nav = document.querySelector(".nav");
  if (!nav) return;
  const on = () => { if (scrollY > 80) nav.classList.add("is-scrolled"); else nav.classList.remove("is-scrolled"); };
  on(); window.addEventListener("scroll", on, { passive: true });
}
```

### 8.2 Cmd+K command palette

See Nómada's `lib/palette.js`. Key principles:
- `<dialog>` semantics or modal pattern with `aria-modal="true"`.
- Listen to `Cmd+K` / `Ctrl+K` globally.
- Fuzzy score: substring + subsequence + position bonus.
- Arrow key navigation, Enter to go, Escape to close.

### 8.3 Side dot navigation with scroll-spy

```html
<nav class="side-dots" aria-label="Sections">
  <a href="#hero" data-label="Inicio"></a>
  <a href="#about" data-label="Sobre"></a>
  <!-- ... -->
</nav>
```
```css
.side-dots {
  position: fixed; top: 50%; right: 1.5rem; z-index: 80;
  display: none; flex-direction: column; gap: 0.7rem;
  transform: translateY(-50%);
}
@media (min-width: 1280px) { .side-dots { display: flex; } }
.side-dots a { width: 18px; height: 18px; display: flex; align-items: center; justify-content: flex-end; }
.side-dots a::after {
  content: ""; width: 6px; height: 6px; border-radius: 50%;
  background: rgba(0,0,0,0.25); transition: width .35s, height .35s, background .35s;
}
.side-dots a.is-active::after { width: 12px; height: 12px; background: var(--accent); }
```
```js
function initSideDots() {
  const dots = document.querySelectorAll(".side-dots a");
  if (!dots.length) return;
  const sections = Array.from(dots).map(d => document.querySelector(d.getAttribute("href"))).filter(Boolean);
  function update() {
    const y = scrollY + innerHeight * 0.4;
    let active = 0;
    sections.forEach((s, i) => { if (s.offsetTop <= y) active = i; });
    dots.forEach((d, i) => d.classList.toggle("is-active", i === active));
  }
  update(); window.addEventListener("scroll", update, { passive: true }); window.addEventListener("resize", update);
}
```

### 8.4 Mobile hamburger fullscreen

```css
.nav-mobile {
  position: fixed; inset: 0; z-index: 90;
  background: var(--ink); color: var(--cream);
  display: grid; place-items: center;
  clip-path: inset(0 0 100% 0);
  transition: clip-path .65s var(--ease-soft);
}
.nav-mobile[aria-hidden="false"] { clip-path: inset(0); }
```

---

# 9. Layout & composition

### 9.1 Bento asymmetric grid (8 cards)

```css
.bento {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}
@media (min-width: 640px) { .bento { grid-template-columns: repeat(2, 1fr); } }
@media (min-width: 960px) {
  .bento {
    grid-template-columns: repeat(12, 1fr);
    grid-template-rows: 280px 280px 280px 280px;
  }
  .bento .card:nth-child(1) { grid-column: span 7; grid-row: span 2; }  /* GRANDE */
  .bento .card:nth-child(2) { grid-column: span 5; grid-row: span 1; }
  .bento .card:nth-child(3) { grid-column: span 5; grid-row: span 1; }
  .bento .card:nth-child(4) { grid-column: span 5; grid-row: span 1; }
  .bento .card:nth-child(5) { grid-column: span 7; grid-row: span 1; }
  .bento .card:nth-child(6) { grid-column: span 4; grid-row: span 1; }
  .bento .card:nth-child(7) { grid-column: span 4; grid-row: span 1; }
  .bento .card:nth-child(8) { grid-column: span 4; grid-row: span 1; }
}
```

⚠️ Each row's spans must sum to **12**.

### 9.2 Strip 3D rotating panels (bilingual flip)

See Restaurante 911's HANDOFF §7.4. Critical CSS:

```css
.strip { perspective: 1800px; perspective-origin: center 60%; }
.strip-row { display: flex; flex-wrap: nowrap; gap: 0.6rem; transform-style: preserve-3d; }
.strip-card {
  flex: 1 1 0; min-width: 0; max-width: 130px; aspect-ratio: 1;
  position: relative; transform-style: preserve-3d;
  animation: stripFlip 7s ease-in-out infinite; animation-delay: var(--d, 0s);
}
.strip-face {
  position: absolute; inset: 0; display: grid; place-items: center;
  -webkit-backface-visibility: hidden; backface-visibility: hidden;
}
.strip-back { transform: rotateY(180deg); }
@keyframes stripFlip {
  0%, 100% { transform: rotateY(0deg); }
  50%      { transform: rotateY(180deg); }
}
/* Reduce on mobile */
@media (max-width: 1023px) { .strip-card:nth-child(n+10) { display: none; } }
@media (max-width: 767px)  { .strip-card:nth-child(n+8)  { display: none; } }
```

### 9.3 Sticky figure narrative

```html
<section class="narrative">
  <div class="grid">
    <figure class="narrative-figure"><img src="..." /></figure>
    <div class="narrative-text">
      <article>...</article><article>...</article><article>...</article>
    </div>
  </div>
</section>
```
```css
@media (min-width: 960px) {
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 5rem; align-items: start; }
  .narrative-figure { position: sticky; top: 8vh; height: 84vh; }
}
```

⚠️ NO `overflow: hidden` on ancestors of sticky elements. Use `overflow: clip` if needed.

### 9.4 CSS Subgrid (for aligned multi-column layouts)

```css
.parent {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 2rem;
}
.child {
  display: grid;
  grid-template-rows: subgrid;          /* inherits from parent */
  grid-row: span 4;
}
```

---

# 10. Color & light

### 10.1 Conic gradient rotating border

See 7.4.

### 10.2 Glow halo following cursor

```css
.has-halo { position: relative; isolation: isolate; }
.has-halo::before {
  content: ""; position: absolute; inset: 0; z-index: -1;
  background: radial-gradient(220px circle at var(--mx, 50%) var(--my, 50%),
                              rgba(196,154,91,.25), transparent 60%);
  opacity: 0; transition: opacity .35s;
  mix-blend-mode: screen;
}
.has-halo:hover::before { opacity: 1; }
```
JS: see tilt 5.1 — same `--mx` / `--my` setting.

### 10.3 Background color morph between sections

```css
html { transition: background .9s ease; background: var(--bg); }
html[data-active-theme="dark"]  { background: var(--bg); }
html[data-active-theme="dark2"] { background: var(--bg-2); }
html[data-active-theme="light"] { background: var(--cream); }
```
```js
function initSectionTheme() {
  const sections = document.querySelectorAll("[data-theme]");
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.intersectionRatio > 0.5) {
        document.documentElement.dataset.activeTheme = e.target.dataset.theme;
      }
    });
  }, { threshold: [0.5] });
  sections.forEach(s => io.observe(s));
}
```

---

# 11. Storytelling

### 11.1 Before/after image slider

```html
<div class="ba-slider" data-ba>
  <img src="before.webp" class="ba-before" />
  <img src="after.webp"  class="ba-after" />
  <input type="range" min="0" max="100" value="50" />
</div>
```

### 11.2 Hover preview video (silent, only plays on hover)

```html
<div class="preview-card" data-preview>
  <video src="clip.mp4" muted loop playsinline preload="none"></video>
  <img src="poster.webp" />
</div>
```
```js
document.querySelectorAll("[data-preview]").forEach(card => {
  const v = card.querySelector("video");
  card.addEventListener("mouseenter", () => v.play());
  card.addEventListener("mouseleave", () => { v.pause(); v.currentTime = 0; });
});
```

---

# 12. Forms & feedback

### 12.1 Realistic submit (simulated)

```html
<form class="cta-form" data-contact-form novalidate>
  <input type="text" name="name" required placeholder="Nombre" />
  <input type="email" name="email" required placeholder="Email" />
  <button type="submit" class="cta-submit">
    <span class="cta-form-label">Enviar</span>
    <span class="cta-form-spinner"></span>
    <svg class="cta-form-check" viewBox="0 0 24 24"><path d="M4 12.5l5 5L20 6" pathLength="1" /></svg>
  </button>
</form>
<div class="cta-success" data-contact-success aria-hidden="true">
  <h3>Recibido. Hablamos pronto.</h3>
  <p data-contact-success-msg></p>
</div>
```

```js
function setupContactForm() {
  const form = document.querySelector("[data-contact-form]");
  const success = document.querySelector("[data-contact-success]");
  if (!form || !success) return;
  const submitBtn = form.querySelector("[type=submit]");
  const msg = document.querySelector("[data-contact-success-msg]");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (form.classList.contains("is-sending")) return;
    if (!form.reportValidity()) return;

    form.classList.add("is-sending");
    submitBtn.disabled = true;

    await new Promise(r => setTimeout(r, 700 + Math.random() * 500));

    const firstName = form.elements.name.value.trim().split(/\s+/)[0];
    if (msg) msg.textContent = `${firstName}, hemos recibido tu nota. Te escribimos en breve.`;

    form.classList.add("is-sent");
    success.setAttribute("aria-hidden", "false");
    success.classList.add("is-visible");
  });
}
```

```css
.cta-form { transition: opacity .55s var(--ease-out), transform .55s var(--ease-soft); }
.cta-form.is-sent { opacity: 0; transform: translateY(-12px); pointer-events: none; }
.cta-form-spinner, .cta-form-check {
  position: absolute; inset: 0; display: grid; place-items: center;
  opacity: 0; pointer-events: none;
}
.cta-form.is-sending .cta-form-label { opacity: 0; }
.cta-form.is-sending .cta-form-spinner { opacity: 1; }
.cta-form-spinner::after {
  content: ""; width: 18px; height: 18px;
  border: 1.5px solid rgba(0,0,0,0.25); border-top-color: var(--ink);
  border-radius: 50%; animation: spin .9s linear infinite;
}
.cta-form-check path {
  stroke: currentColor; stroke-width: 2; fill: none;
  stroke-dasharray: 1; stroke-dashoffset: 1;
  transition: stroke-dashoffset .55s var(--ease-out);
}

.cta-success {
  position: absolute; left: 50%; top: 50%;
  transform: translate(-50%, -40%);
  opacity: 0; pointer-events: none;
  transition: opacity .8s var(--ease-out) .25s, transform .9s var(--ease-soft) .25s;
}
.cta-success.is-visible {
  opacity: 1; transform: translate(-50%, -50%); pointer-events: auto;
}
```

### 12.2 Floating labels

```css
.field {
  position: relative;
}
.field input {
  width: 100%; padding: 1.4rem 1rem 0.5rem; border: 1px solid var(--line);
  background: transparent; color: inherit;
}
.field label {
  position: absolute; left: 1rem; top: 50%; transform: translateY(-50%);
  pointer-events: none; transition: all .25s var(--ease-out);
  color: var(--ink-mute);
}
.field input:focus + label,
.field input:not(:placeholder-shown) + label {
  top: 0.4rem; transform: none; font-size: 0.7rem; letter-spacing: 0.18em; text-transform: uppercase;
}
```

---

## Combining effects — guidelines

- **4–5 effects per page.** Add up the count from the categories above and verify you didn't exceed.
- **One signature.** Pick one effect to be "the thing" — the other 3–4 support it.
- **Don't combine bilingual scramble + Cmd+K + side dots + cursor + tilt + ...** That's a SaaS dashboard, not editorial.
- **Avoid effects that fight each other.** Lenis + scroll-snap don't mix. Tilt + magnetic on the same element compete. Particle system + mesh gradient over-saturate.
- **The mobile experience drops some effects automatically.** 3D scenes, particles, magnetic, custom cursor → `hover: none` skips them. Your job is to make the mobile composition still feel intentional.
