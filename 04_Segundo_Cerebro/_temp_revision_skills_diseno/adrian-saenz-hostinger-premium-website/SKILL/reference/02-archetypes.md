# Visual Archetypes — pick ONE per project

This skill must produce **diverse outputs**. The biggest risk is that every web ends up looking like the three reference projects (Nómada, Restaurante, Gambit). To prevent that, every new project must explicitly map to one of the **10 archetypes** below. Each archetype has a distinct visual DNA: palette family, typography pairing, layout topology, signature effects, hero pattern, image treatment.

**Do not combine two archetypes.** Mixing produces confused webs. Pick one, commit to it.

**Rotation rule:** track the last 5 archetypes used. If the current brief points to one used recently, force the next-most-suitable instead. See `06-diversity-guardrails.md`.

---

## How to read this file

For each archetype:
- **Identity** — what it feels like in one sentence.
- **When to choose** — industries / briefs that fit naturally.
- **Palette family** — color tokens.
- **Typography pairing** — display + body + accent.
- **Layout topology** — how sections stack.
- **Signature effects** — 4–5 specific effects from the catalog (no more).
- **Hero pattern** — the recipe for first viewport.
- **Image treatment** — how photos are framed.
- **Avoid** — explicit rules to keep this archetype distinct.

---

# Archetype 01 — Editorial Light Cream

**Reference: Nómada (agencia de viajes)**

### Identity
A travel-magazine-on-a-website. Cream backgrounds, plenty of breathing room, large editorial photography, italic serif headlines, restraint over saturation.

### When to choose
- Travel agencies, hospitality (hotels, retreats), boutique experiences.
- Wellness, slow lifestyle.
- Boutique cafés, ceramics, artisanal crafts.
- Wedding planners, bespoke events.
- Multi-language / multi-script content (Japanese, Arabic, Cyrillic destinations).

### Palette family

```css
:root {
  --bg:        #f4efe6;   /* warm cream */
  --bg-2:      #e8dfd0;   /* sand */
  --paper:     #ffffff;
  --ink:       #1a1a1a;
  --ink-soft:  #2a2a2a;
  --ink-mute:  #6b6b6b;
  --accent:    #b85c3a;   /* terracotta — single warm accent */
  --accent-2:  #4a5d3a;   /* moss — secondary cool accent */
  --line:      rgba(26,26,26,0.12);
}
```

### Typography pairing

- **Display:** Fraunces (variable, opsz + wght + SOFT). Italic for emphasis.
- **Body:** Inter (300–500).
- **Multilingual stack:** add Noto Serif JP, Noto Naskh Arabic, Noto Sans Georgian, Noto Serif Devanagari, Noto Serif Ethiopic, Noto Serif as fallbacks for `.card-title` / multi-script content.

### Layout topology

1. Sticky transparent nav, solidifies on scroll.
2. Full-bleed hero with single large image, eyebrow + serif headline + italic subtitle + search field.
3. Manifesto section (single asymmetric two-column: small num left, paragraph right).
4. **Bento grid 8-cards asymmetric** for destinations / products.
5. Marquee ticker (city names / categories) between sections.
6. Horizontal carousel for experiences (`scroll-snap-type: x mandatory`).
7. Testimonials with split 50/50 photo + quote, auto-rotating.
8. Diary / blog list (3 horizontal article cards).
9. Final CTA with mesh gradient + form.
10. Footer with credits-photo subtle link.

### Signature effects (pick exactly these)

1. **Bilingual scramble** on card titles (original alphabet → Spanish on hover).
2. **Bento grid hover**: card lifts with terracotta halo shadow + tilt 9° + chromatic aberration.
3. **Marquee ticker** seamless between sections.
4. **Custom cursor**: two clean circles, ring with mix-blend-mode difference.
5. **Cmd+K command palette** for navigation.

### Hero pattern

```html
<section class="hero">
  <img src="hero.webp" class="hero-bg" />
  <div class="hero-overlay"></div>
  <div class="hero-content">
    <p class="kicker">Brand Type · Year</p>
    <h1 class="hero-title">Editorial line.<br><em>Italic emphasis.</em></h1>
    <p class="hero-sub">15-word italic subtitle that explains nothing but evokes.</p>
    <form class="hero-search">
      <input placeholder="¿A dónde te llama el deseo?" />
      <button type="submit">⌕</button>
    </form>
  </div>
</section>
```

### Image treatment

- **Aspect ratios:** 4:5 (portrait cards), 16:8 (wide hero), 1:1 (gallery thumbs).
- **Filter:** none on hero. Cards: `saturate(1.15)` + grain SVG overlay 18% opacity.
- **Hover:** `transform: scale(1.12)` + `filter: saturate(1.18) brightness(1.08)`.

### Avoid

- ❌ Dark backgrounds (use 02 instead).
- ❌ 3D scenes / Three.js.
- ❌ Brutalist typography.
- ❌ Heavy gradients (the cream is the gradient).
- ❌ Cmd+K + side dot nav + scroll progress all together (too dashboard-y).

---

# Archetype 02 — Editorial Dark Warm

**Reference: 911 Restaurante**

### Identity
Premium dark editorial. Warm-toned dark background (never pure black), single warm accent, glyph signature unicode characters as cultural marker, mesh gradient breathing in the hero, scroll horizontal showcase pinned.

### When to choose
- Restaurants, wine bars, izakaya, cocktail bars.
- Members-only clubs, speakeasies.
- Dark luxury (jewelry, hifi, fragrance).
- Hospitality with strong night identity.

### Palette family

```css
:root {
  --bg:       #0E0B09;   /* warm-tinted near-black, NEVER #000 */
  --bg-2:     #15110E;
  --bg-3:     #1E1813;   /* card */
  --cream:    #F2EBDA;   /* text on dark — never pure white */
  --cream-2:  #DDD2BC;
  --cream-3:  #8B7E68;   /* metadata */
  --accent:   #C5301E;   /* CHANGE per brand: rojo terracota / matcha verde / ámbar */
  --accent-2: #A82516;
  --gold:     #C49A5B;   /* warm secondary */
  --line:     rgba(242,235,218,.12);
}
```

### Typography pairing

- **Display:** Fraunces (variable). Italic with `SOFT 100` axis for the warmest, softest cursive.
- **Body:** Inter.
- **Glyph:** Noto Serif JP (or appropriate script) for the cultural signature characters.

### Layout topology

1. Splash loader (CSS+JS double safety).
2. Hero centered: kicker + glyph signature (e.g., 九一一) + serif title + rating + CTAs.
3. Concept section (single column editorial — figure ancha 16:8 + 3 pillar columns).
4. **Showcase pinned scroll horizontal** (8–12 cards).
5. **Strip 3D rotating panels** — bilingual flip cards.
6. Reservation form with realistic submit + SVG check.
7. Map + info section.
8. Footer with credits.

### Signature effects (pick exactly these)

1. **Mesh gradient** animado en hero con `@property --mesh-angle` (conic + radial blur 70px).
2. **Showcase pinned horizontal** scroll (ScrollTrigger pin + scrub).
3. **Strip 3D rotating** bilingual cards (`backface-visibility` + delays escalonados).
4. **Tilt 3D 7° max** en cards principales con halo radial siguiendo cursor.
5. **Form submit cinematográfico** con SVG path drawing en success.

### Hero pattern

```html
<section class="hero">
  <div class="hero-bg"><img src="hero.webp" /><div class="hero-bg-tint"></div></div>
  <div class="hero-mesh"></div>     <!-- mesh gradient animado -->
  <div class="hero-grain"></div>
  <div class="hero-inner">
    <div class="hero-meta"><span class="dot"></span><span>Andorra · Abierto</span></div>
    <span class="hero-glyph">九一一</span>
    <h1 class="hero-title">
      <span>Cocina <em>japo-mediterránea</em>.</span>
      <span>Para compartir.</span>
    </h1>
    <p class="hero-loc">Escaldes-Engordany</p>
    <div class="hero-foot">
      <div class="hero-rating"><span data-count-to="4.7">4,7</span> ★ · <span data-count-to="140">140</span> reseñas</div>
      <div class="hero-actions">
        <a class="btn btn-primary">Reservar</a>
        <a class="btn btn-ghost">Ver carta</a>
      </div>
    </div>
  </div>
</section>
```

### Image treatment

- **Aspect:** mostly 16:9 wide and 4:5 portrait.
- **Filter on hero:** `saturate(1.05) contrast(1.05)` + tint overlay rgba(14,11,9,0.55–0.95).
- **Hover on cards:** `scale(1.06)` + `saturate(1.18)`.

### Avoid

- ❌ Cream / light backgrounds (use 01).
- ❌ Pure black `#000`.
- ❌ Multiple competing accents (one accent + one gold).
- ❌ Bento asymmetric grid of images (too 2024).
- ❌ Custom cursor with text labels.

---

# Archetype 03 — Cinematic 3D Storytelling

**Reference: The Gambit (newsletter landing)**

### Identity
A persistent Three.js scene fills the viewport. As the user scrolls, the camera orbits, zooms, changes FOV. Content sections float above the 3D. Cinematic lighting (4 sources), warm fog, sub-exposed tone mapping.

### When to choose
- Newsletters, premium publications.
- Niche-elite products (chess, watches, audiophile).
- Premium services with a "story" (sommelier, atelier, design studio).
- Anything that benefits from a metaphorical 3D centerpiece.

### Palette family

```css
:root {
  --bg-deep:       #050302;   /* deep dark with warm tint */
  --bg-soft:       #0f0904;
  --accent-bright: #d4af37;   /* metallic — gold / copper / brass / chrome */
  --accent-mid:    #c9a961;
  --accent-dark:   #8a6f33;
  --text:          #f4ead5;   /* cream, never #fff */
  --text-muted:    rgba(244,234,213,0.7);
  --text-dim:      rgba(244,234,213,0.4);
}
```

### Typography pairing

- **Display:** Playfair Display, Cormorant, EB Garamond, Italiana — italic 500.
- **Body:** Inter / Manrope / Söhne.
- **Mono accent:** JetBrains Mono / IBM Plex Mono — for kickers, dates, metrics, badges.

### Layout topology

1. Persistent canvas (3D scene) `position: fixed; inset: 0; z-index: 0`.
2. Hero: kicker mono + serif italic h1 with metallic accent on key word.
3. Splits texto+visual using `lookSide` camera trick (subject moves left, text right; or reversed).
4. List "archive" with mono dates and metallic accent on titles.
5. Testimonials in cards with `backdrop-filter: blur(12px)` + opaque background.
6. Lead magnet / form with `rotateY` slight tilt.
7. Pricing tiers (if applicable).
8. FAQ accordion (one item open by default).
9. Final CTA + footer.

### Signature effects (pick exactly these)

1. **Three.js scene with primitives** (no GLTF) + 4-light cinematic lighting.
2. **Scroll-driven camera keyframes** with `pos`/`lookAt`/`fov`/`exposure`/`lookSide`.
3. **8 contrast layers** for text legibility over 3D (scrim, vignette, grain, halos, text-shadow…).
4. **Floating decoration** (6 instances of secondary objects with sin/cos float).
5. **Smooth scroll lerp** of progress (0.05 factor).

### Hero pattern

```html
<section class="hero">
  <div class="kicker">Edition 042 · 2026</div>
  <h1>El boletín que <em>juega contigo</em>.</h1>
  <p>Editorial sobre lo que importa, antes de que importe.</p>
  <a class="btn-metallic">Suscribirse</a>
</section>
<canvas id="three-canvas"></canvas>
<div class="scrim"></div>
<div class="vignette"></div>
<div class="grain"></div>
```

### Image treatment

- **Almost no photography.** The 3D scene IS the imagery.
- If photos are used: tiny inserts in archive cards, b/w + accent tint.

### Critical contrast layers (mandatory)

```css
.scrim    { position: fixed; inset: 0; z-index: 1; background: rgba(5,3,2,0.28); pointer-events: none; }
.vignette { position: fixed; inset: 0; z-index: 1; background:
  radial-gradient(ellipse at center, transparent 30%, rgba(5,3,2,0.4) 70%, rgba(5,3,2,0.82) 100%),
  linear-gradient(180deg, rgba(5,3,2,0.55) 0%, transparent 30%, transparent 70%, rgba(5,3,2,0.7) 100%);
  pointer-events: none; }
.grain    { position: fixed; inset: 0; z-index: 2; opacity: 0.05; mix-blend-mode: overlay; pointer-events: none;
            background-image: url('data:image/svg+xml;…'); }

.split-text {
  position: relative;
  text-shadow: 0 2px 24px rgba(0,0,0,0.85), 0 1px 4px rgba(0,0,0,0.9);
}
.split-text::before {
  content: ""; position: absolute; inset: -50px -60px;
  background: radial-gradient(ellipse at center, rgba(5,3,2,0.88) 0%, rgba(5,3,2,0.6) 60%, transparent 100%);
  filter: blur(8px); z-index: -1;
}

.testimonial-card { background: rgba(5,3,2,0.92); backdrop-filter: blur(12px); }
```

Tone mapping: `renderer.toneMappingExposure = 0.78`. Fog: `THREE.FogExp2(0x080604, 0.032)`.

### Avoid

- ❌ Light backgrounds.
- ❌ `#fff` text (use cream `#f4ead5`).
- ❌ Inline 3D embedded in mid-page (the scene is fixed background).
- ❌ More than 6 floating decoration instances.
- ❌ Realistic photography next to the 3D — they fight visually.

---

# Archetype 04 — Glassmorphism Modern

### Identity
Soft pastels (peach, mint, lavender, sky), translucent cards with `backdrop-filter: blur`, rounded shapes, gentle gradients. iOS / Apple Vision Pro adjacent.

### When to choose
- Tech / SaaS / startup.
- Boutique product (cosmetics, candles, audio).
- Wellness apps, mindfulness.
- Premium luxury with soft tone (not aggressive luxury).
- Crypto / finance with a friendly face.

### Palette family

```css
:root {
  --bg:       #f5f0ea;   /* warm off-white */
  --bg-2:     linear-gradient(135deg, #ffd6a5 0%, #ffadad 50%, #bdb2ff 100%);
  --glass:    rgba(255, 255, 255, 0.45);
  --glass-2:  rgba(255, 255, 255, 0.25);
  --ink:      #1f2937;
  --ink-soft: #4b5563;
  --accent:   #ff7a59;   /* coral / soft warm */
  --accent-2: #6366f1;   /* lavender / soft indigo */
  --line:     rgba(31, 41, 55, 0.12);
}
```

### Typography pairing

- **Display:** Söhne / Inter Display / GT Walsheim style — geometric sans, weight 600.
- **Body:** Inter (400).
- **Optional accent:** Migra Italic for a single italicized word in headlines.

### Layout topology

1. Floating glass nav (always visible, blur background).
2. Hero with **gradient mesh background** + huge geometric sans h1 + product image floating with shadow.
3. Feature cards: 3-up grid with glass cards (translucent + blur).
4. Testimonial section: large card centered, glassmorphic.
5. Pricing tiers in glass cards.
6. FAQ accordion in glass.
7. Email-capture CTA.
8. Footer minimal.

### Signature effects (pick exactly these)

1. **Animated mesh gradient** background covering the page (5 stops, 30s loop).
2. **Glass cards** with `backdrop-filter: blur(20px) saturate(180%)` + 1px white border.
3. **Floating product** (image with `filter: drop-shadow(0 60px 80px rgba(0,0,0,0.3))` + slow Y bob).
4. **Magnetic CTA buttons** (subtle, strength 0.2).
5. **Animated underline** on nav links sliding between hovers.

### Hero pattern

```html
<section class="hero">
  <div class="hero-mesh"></div>            <!-- animated mesh gradient -->
  <h1>Sistemas <em>simples</em><br>para problemas complejos.</h1>
  <p class="hero-sub">15-word value prop.</p>
  <a class="btn-glass">Empezar gratis →</a>
  <img src="product.webp" class="hero-product" />
</section>
```

### CSS critical bits

```css
.hero-mesh {
  position: absolute; inset: 0; z-index: -1;
  background:
    radial-gradient(at 20% 30%, #ffd6a5 0%, transparent 50%),
    radial-gradient(at 80% 70%, #bdb2ff 0%, transparent 50%),
    radial-gradient(at 50% 90%, #ffadad 0%, transparent 50%);
  filter: blur(60px) saturate(150%);
  animation: meshDrift 30s ease-in-out infinite;
}
@keyframes meshDrift {
  0%, 100% { transform: scale(1) rotate(0deg); }
  50%      { transform: scale(1.2) rotate(180deg); }
}

.glass-card {
  background: var(--glass);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255,255,255,0.5);
  border-radius: 24px;
  /* SOLID FALLBACK if backdrop-filter unsupported */
  background: rgba(255,255,255,0.7);
}
@supports (backdrop-filter: blur(20px)) {
  .glass-card { background: var(--glass); }
}
```

### Image treatment

- Product photos with strong drop-shadow to "float".
- No grain overlay (it would dirty the soft palette).
- Lifestyle photos: light + airy + saturated +5%.

### Avoid

- ❌ Dark backgrounds.
- ❌ Heavy serif italic headlines (the geometric sans is the voice).
- ❌ Editorial magazine layouts.
- ❌ Text-shadows (the glass IS the depth).
- ❌ More than 3 colors in the gradient mesh.

---

# Archetype 05 — Mouse-Reactive Gradient

### Identity
A single big gradient mesh fills the viewport and follows the cursor (or scroll progress). Massive sans typography. Monochrome palette + ONE neon accent. Brutalist-adjacent but warmer.

### When to choose
- Tech startups, AI products, dev tools.
- Crypto, web3 (the kind that wants to look "credible").
- Independent agencies (design, branding).
- Bold portfolio of a single creator.

### Palette family

```css
:root {
  --bg:     #0a0a0a;   /* near-black, slightly warm */
  --bg-2:   #1a1a1a;
  --ink:    #fafafa;   /* near-white */
  --mute:   #a3a3a3;
  --accent: #00ff88;   /* neon green / electric blue / hot pink — pick one */
  --gradient-1: #ff006e;
  --gradient-2: #8338ec;
  --gradient-3: #3a86ff;
  --gradient-4: #06ffa5;
}
```

### Typography pairing

- **Display:** GT Sectra / Editorial Old (serif display) OR ABC Diatype Mono (mono display) — choose one.
- **Body:** Inter (400) or JetBrains Mono (400) — match the display.
- Either super-serif-display + sans-body, OR all-mono. Don't mix mono display with serif body.

### Layout topology

1. Hero with mouse-reactive gradient + huge h1 (10+ vw font-size).
2. Manifesto / about — single big paragraph centered, 60ch max, big size (1.5rem+).
3. Work / portfolio: vertical list of project rows (no grid). Each row: project name + year + brief. Click → expands.
4. Stats counter (animated count-up).
5. Process / values — 3 numbered blocks.
6. Contact: email link as huge h2 with hover underline.
7. Footer minimal: copyright + social.

### Signature effects (pick exactly these)

1. **Mouse-reactive gradient mesh** (radial gradients positioned at cursor x/y).
2. **Massive type with hover invert** — h1/h2 invert colors on hover.
3. **Project list rows** that expand vertically on click (accordion).
4. **Count-up numbers** for stats.
5. **Animated underline** on the contact email link.

### Hero pattern

```html
<section class="hero">
  <div class="hero-gradient" data-mouse-gradient></div>
  <h1 class="hero-title">
    Construimos<br>
    <em>productos</em><br>
    que importan.
  </h1>
</section>
```

```css
.hero-gradient {
  position: absolute; inset: 0; z-index: -1;
  background:
    radial-gradient(circle 600px at var(--mx, 50%) var(--my, 50%),
      var(--gradient-1) 0%, transparent 50%),
    radial-gradient(circle 800px at calc(var(--mx, 50%) + 10%) calc(var(--my, 50%) - 10%),
      var(--gradient-2) 0%, transparent 50%),
    var(--bg);
  filter: blur(40px) saturate(150%);
  transition: background 0.3s ease;
}
```

```js
// JS: mouse position
document.addEventListener("mousemove", (e) => {
  const x = (e.clientX / window.innerWidth) * 100;
  const y = (e.clientY / window.innerHeight) * 100;
  document.documentElement.style.setProperty("--mx", x + "%");
  document.documentElement.style.setProperty("--my", y + "%");
});
```

### Image treatment

- Almost no photography. Type-driven entirely.
- If used: project thumbnails in vertical list, 16:10, hover reveals.
- Black/white or duotone (accent + black).

### Avoid

- ❌ Cream / light backgrounds.
- ❌ Editorial italic serif — only display serif (or all-mono).
- ❌ Bento grids, mesh gradients without mouse interaction (use 04 for that).
- ❌ Many photos.
- ❌ Tilt 3D (clashes with the flat brutalist energy).

---

# Archetype 06 — Magazine Multi-Page

### Identity
A real multi-page editorial magazine site. Home + articles + archive. Drop caps, justified body text, image cutouts, vertical rhythm strict. Print-inspired.

### When to choose
- Online magazines, journals, newspapers.
- Long-form publications (essays, newsletters with archive).
- Cultural institutions (gallery, foundation).
- Author portfolios with extensive writing.

### Palette family

```css
:root {
  --bg:        #f8f5f0;   /* warm paper white */
  --bg-2:      #efe9dd;
  --ink:       #1a1714;   /* warm near-black */
  --ink-soft:  #3a342e;
  --ink-mute:  #6e6760;
  --accent:    #a02824;   /* magazine red */
  --line:      #1a1714;   /* full opacity for hairlines */
}
```

### Typography pairing

- **Display:** Bodoni Moda / Tiempos Headline / Playfair Display — high-contrast serif.
- **Body:** Source Serif / Tiempos Text / Spectral — readable serif (yes, body is serif here).
- **Sans accent:** Founders Grotesk / Söhne for kickers, dates, metadata.

### Layout topology

#### `index.html` (cover):
1. Masthead with logo + issue number + date.
2. Hero article: huge headline + author + image + lede (60-word teaser).
3. 3-column grid of article previews.
4. "Departments" section (sub-categories).
5. Subscribe CTA.
6. Footer with archive link.

#### `article.html` (single post):
1. Same masthead.
2. Article hero: kicker (CATEGORY) + title + author + date + reading time.
3. Featured image (full-bleed or 4:3 inset).
4. Body text in 1 column 70ch max with **drop cap** on first paragraph.
5. Pull quotes (large italic indented).
6. Image insertions.
7. End-of-article author bio.
8. Related articles (3 cards).

#### `archive.html`:
1. Masthead.
2. List of all articles with date, category, title. Filter by category.
3. Pagination.

### Signature effects (pick exactly these)

1. **Drop cap** large italic accent on lede paragraph.
2. **Pull quote** with quotation mark decorative + huge italic text.
3. **Reading progress bar** (top of article page).
4. **Animated underline** on category links + masthead nav.
5. **Subtle parallax** on featured images (max 20px shift).

### Hero pattern (cover)

```html
<header class="masthead">
  <div class="issue">No. 042 · Marzo 2026</div>
  <h1 class="brand">La Crónica</h1>
  <nav>
    <a>Cultura</a><a>Diseño</a><a>Política</a><a>Tecnología</a>
  </nav>
</header>
<article class="hero-article">
  <p class="kicker">REPORTAJE LARGO</p>
  <h2>El siglo XXI <em>todavía no ha empezado</em>.</h2>
  <p class="byline">Por <strong>María Solana</strong> · 15 min de lectura</p>
  <img src="hero.webp" />
  <p class="lede"><span class="dropcap">E</span>n algún momento de los últimos años, la modernidad…</p>
</article>
```

### Image treatment

- Aspect: 16:9 hero, 3:2 inserts, 1:1 author photos.
- Filter: subtle warm tint overlay (opacity 5% sepia).
- Captions in italic small serif below image.

### Avoid

- ❌ Animations on the article body.
- ❌ Glassmorphism, dark backgrounds, neon accents.
- ❌ Full-bleed CSS. Margins matter (typography is mathematical).
- ❌ Buttons with shadows (use underlines and minimal borders).
- ❌ 3D, video heroes.

---

# Archetype 07 — Brutalist Grid

### Identity
Strict CSS grid, oversized type, monospace, primary colors. No curves. Anti-elegant on purpose. Looks "raw" but is precisely composed.

### When to choose
- Studios that want to project edge / non-conformist.
- Cultural / underground events.
- Indie design publications.
- Architecture firms.
- Avant-garde galleries.
- Manifestos, zines.

### Palette family

```css
:root {
  --bg:     #ffffff;   /* pure white */
  --ink:    #000000;   /* pure black */
  --accent: #ff0000;   /* primary red */
  --accent-2: #0000ff; /* primary blue */
  --accent-3: #ffff00; /* primary yellow */
  /* Or mono palette: only black + white + ONE primary */
}
```

### Typography pairing

- **Display + body:** ABC Diatype Mono / IBM Plex Mono / JetBrains Mono — ALL mono.
- OR **Display:** Helvetica Neue Condensed Bold (super big sizes).
- **Body:** Inter (also as accent OK).

### Layout topology

1. Strict CSS grid: 12 columns, gutter 1px, hairline borders visible everywhere.
2. Header: logo + nav inline, NO logo center.
3. Sections delimited by horizontal rules `border-top: 1px solid #000`.
4. Content blocks numbered (`01.`, `02.`, `03.`).
5. Each block: kicker + headline + paragraph + optional image.
6. Footer: contact info in monospace block.

### Signature effects (pick exactly these)

1. **Horizontal scroll text marquee** for headlines (mono, 200vh tall).
2. **Hover invert** — black bg → white bg on link hover (no gradient, instant).
3. **Cursor follows with monospace coordinates** (e.g., `[423, 120]` displayed near cursor).
4. **Number counters** in monospace for stats.
5. **Strict grid lines** — visual `1px` lines that act as design element.

### Hero pattern

```html
<section class="hero">
  <div class="grid-12">
    <div class="col-span-7">
      <p class="kicker">01. Manifiesto</p>
      <h1>Diseñamos para<br>la <em>incomodidad</em>.</h1>
    </div>
    <div class="col-span-5">
      <p>Lorem ipsum etc en monospace.</p>
    </div>
  </div>
</section>
```

```css
.grid-12 {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 1px;
  background: var(--ink);   /* lines */
}
.grid-12 > * {
  background: var(--bg);
  padding: 2rem;
}
```

### Image treatment

- Images cropped tight, no padding.
- Black-and-white only, OR full color.
- Hover: invert filter (`filter: invert(1)`) for shock effect.

### Avoid

- ❌ Rounded corners. EVER. `border-radius: 0` only.
- ❌ Shadows.
- ❌ Gradients.
- ❌ Curves (no `border-radius`, no transforms with `rotate()` other than 0/90/180).
- ❌ Italic serif (only mono or geometric sans).

---

# Archetype 08 — Liquid Wave Backgrounds

### Identity
Animated SVG waves, organic curves, ocean-inspired palette. Smooth and flowing. Perfect for products that want to feel "natural" and "alive".

### When to choose
- Wellness / hydration products.
- Spa / hotel coastal.
- Surf brands, water sports.
- Mineral water, organic drinks.
- Sustainable / eco brands.

### Palette family

```css
:root {
  --bg:        #e0f7fa;   /* pale aqua */
  --bg-deep:   #006064;   /* deep teal */
  --ink:       #001f25;
  --accent:    #00bfa5;   /* mint */
  --accent-2:  #ffd166;   /* sun yellow */
  --line:      rgba(0,31,37,0.12);
}
```

### Typography pairing

- **Display:** GT Walsheim / Inter Display — rounded geometric sans.
- **Body:** Inter / Söhne.
- Optional **organic accent:** Caveat (handwritten) for one-line labels.

### Layout topology

1. Hero with full-bleed animated SVG wave background + product floating + headline.
2. About / story — alternating left/right panels with wave dividers.
3. Process / steps with wave-shaped section transitions.
4. Testimonials with wave card backgrounds.
5. CTA with wave underline.
6. Footer with wave top.

### Signature effects (pick exactly these)

1. **Animated SVG waves** as section dividers (CSS transform, not JS).
2. **Floating product image** with slow Y bob + drop shadow.
3. **Liquid blob shapes** (CSS `border-radius: 38% 62% 63% 37% / 41% 44% 56% 59%`) animated.
4. **Smooth scroll** with extra bounce easing.
5. **Wave reveal** on scroll (image emerges from bottom with wavy clip-path).

### Hero pattern

```html
<section class="hero">
  <svg class="hero-wave" viewBox="0 0 1440 800" preserveAspectRatio="none">
    <path d="…" fill="url(#wave-gradient)"></path>
  </svg>
  <div class="hero-content">
    <h1>Hidratación <em>real</em>.</h1>
    <p>Agua mineral con minerales reales.</p>
  </div>
  <img src="bottle.webp" class="hero-product" />
</section>
```

### Image treatment

- Soft, washed-out filter (saturation -10%).
- Liquid masks applied (`clip-path: polygon` with curves).
- Rounded edges everywhere.

### Avoid

- ❌ Brutalist hard edges.
- ❌ Dark backgrounds.
- ❌ Mono fonts.
- ❌ Strict grids.
- ❌ Sharp shadows.

---

# Archetype 09 — Newspaper Editorial

### Identity
Inspired by classic newspapers: dense layout, multi-column body text, image cutouts, drop caps, hairline borders. Like reading a Sunday paper.

### When to choose
- Long-form journalism.
- Op-ed sites, opinion publications.
- Politics, history, culture deep-dives.
- Old-school authority brands (legal firms, classical music).

### Palette family

```css
:root {
  --bg:     #faf7f0;   /* newsprint cream */
  --ink:    #16140e;
  --accent: #960018;   /* newspaper red */
  --line:   #16140e;
}
```

### Typography pairing

- **Display:** Stanley / Bodoni / Tiempos Headline.
- **Body:** Source Serif / Lyon / Spectral.
- **Sans:** Söhne / Founders Grotesk for kickers and metadata only.

### Layout topology

1. Newspaper-style masthead.
2. Hero: huge headline + sub-deck + 2-column body text.
3. **Multi-column body** (`column-count: 2` or `3`).
4. Image cutouts within columns (with `float: left/right` + caption).
5. Pull quotes break columns.
6. End: byline, date, related stories.

### Signature effects (pick exactly these)

1. **Drop cap** on first paragraph (HUGE, 4–5 lines tall).
2. **Multi-column layout** with `column-rule: 1px solid var(--ink)`.
3. **Pull quotes** with quotation marks as decorative element.
4. **Hairline horizontal rules** between sections.
5. **Date/byline metadata** in small caps sans.

### Hero pattern

```html
<header class="masthead">
  <div class="hairline-top"></div>
  <h1 class="brand-newspaper">El Globo</h1>
  <p class="issue">Año XXIV · No. 1.234 · Lunes 15 de marzo de 2026</p>
  <div class="hairline-bottom"></div>
</header>
<article class="hero-article">
  <p class="kicker">EDITORIAL</p>
  <h2 class="huge-serif">El silencio como <em>estrategia política</em>.</h2>
  <p class="deck">El subdeck explica en una frase de 25 palabras la tesis central del artículo.</p>
  <div class="multi-column">
    <p><span class="dropcap">L</span>orem ipsum dolor sit amet…</p>
    <!-- continues across 2-3 columns -->
  </div>
</article>
```

### Image treatment

- Black-and-white photos.
- Captions in italic.
- Cutouts integrated within text columns (`float: left; margin: 0 1em 1em 0`).

### Avoid

- ❌ Animations beyond reading progress.
- ❌ Modern accent colors (only newspaper red).
- ❌ Sans-serif body.
- ❌ Backdrop blur.
- ❌ Wide layouts (max-width 920px is generous).

---

# Archetype 10 — Spline Embed Premium

### Identity
A single Spline 3D scene as the hero centerpiece (embedded iframe or runtime). The rest of the page is minimal — the 3D does all the talking.

### When to choose
- Product launches (when there's a hero product).
- Premium consumer goods (sneakers, watches, gadgets).
- Branding agencies showcasing capability.
- Anything that benefits from a 3D rotating product.

### Palette family

```css
:root {
  --bg:         #0a0a14;   /* deep navy-black */
  --bg-2:       linear-gradient(180deg, #0a0a14 0%, #1e1b3a 100%);
  --ink:        #f0f0f5;
  --ink-soft:   rgba(240,240,245,0.7);
  --accent:     #00d9ff;   /* electric / iridescent */
  --accent-2:   #ff00ea;   /* magenta complement */
  --gradient:   linear-gradient(135deg, #00d9ff 0%, #ff00ea 100%);
}
```

### Typography pairing

- **Display:** ABC Diatype Mono OR Inter Display (geometric).
- **Body:** Inter (300, light).
- Tiny letter-spacing on display, generous on body.

### Layout topology

1. Hero: Spline iframe full-bleed + minimal text overlay (brand name + 1-line tagline).
2. Features: 3 sections with text + small inline 3D detail (or static product photos).
3. Specs / details in mono table.
4. Testimonials minimal.
5. CTA with iridescent gradient button.
6. Footer.

### Signature effects (pick exactly these)

1. **Spline iframe embed** OR a CSS-based fake 3D rotating product.
2. **Iridescent gradient buttons** (multi-color animated `background-position`).
3. **Mouse-follow glow** behind product (radial gradient at cursor).
4. **Letter-by-letter typewriter** on tagline reveal.
5. **Subtle parallax** on body sections (max 30px).

### Hero pattern

```html
<section class="hero">
  <iframe src="https://my.spline.design/your-scene/" class="spline-frame"></iframe>
  <div class="hero-overlay">
    <span class="brand">DEXTER 01</span>
    <h1>El reloj que <em>no necesitas</em>.</h1>
  </div>
</section>
```

### CSS critical bits

```css
.spline-frame {
  position: absolute; inset: 0;
  width: 100%; height: 100%;
  border: 0;
  pointer-events: auto; /* let user rotate the model */
}
```

### Image treatment

- Photos rare. When used: macro shots, dark background, hard rim light.

### Avoid

- ❌ Multiple 3D scenes (only one).
- ❌ Editorial italic serif.
- ❌ Cream / warm backgrounds.
- ❌ Brutalist grid (clashes with the smooth 3D).
- ❌ Bento grid.

### Notes on Spline

- For static deploy: export Spline scene → host on Spline's CDN → embed via iframe with their share URL.
- Spline iframes work everywhere including `file://`.
- Alternative if no Spline scene available: use CSS-only fake 3D with `transform: rotateY` perspective on a product image, animated.

---

## Quick reference table — picking an archetype

| Industry | Default | Alternative |
|---|---|---|
| Restaurant / izakaya / fine dining | 02 Dark Warm | 09 Newspaper (for storied institutions) |
| Travel agency / boutique experiences | 01 Cream | 06 Magazine |
| Newsletter / magazine | 03 3D Cinematic | 06 Magazine, 09 Newspaper |
| SaaS / tech / dev tools | 05 Mouse Gradient | 04 Glassmorphism |
| Wellness / hydration / spa | 08 Liquid Wave | 04 Glassmorphism |
| Studio / agency / portfolio | 07 Brutalist | 03 3D, 05 Mouse |
| Boutique product launch | 10 Spline | 04 Glassmorphism |
| Editorial publication | 06 Magazine | 09 Newspaper |
| Cultural / gallery / event | 07 Brutalist | 09 Newspaper |
| Coffee / café / artisan | 01 Cream | 06 Magazine |
| Hotel boutique | 01 Cream | 02 Dark Warm |
| Wine bar / sommelier | 02 Dark Warm | 03 3D |
| Crypto / web3 | 05 Mouse | 10 Spline |
| Architecture | 07 Brutalist | 09 Newspaper |
| Music classical / venue | 03 3D | 06 Magazine |
| Surf / outdoor | 08 Liquid Wave | 05 Mouse |
| Personal brand creator | 05 Mouse | 07 Brutalist |
| Photography portfolio | 06 Magazine | 09 Newspaper |
| Law firm / professional | 09 Newspaper | 02 Dark Warm |

---

## Final rule

If the brief truly does not fit any archetype, **don't invent a new one** in the moment. Pick the closest match and adapt the **palette and microcopy**, NOT the layout topology. The 10 archetypes are the design vocabulary; the rest is content.

If after 3 prompts you've seen the same archetype twice for similar-feeling briefs, force the next-most-suitable. Diversity is part of the deliverable.
