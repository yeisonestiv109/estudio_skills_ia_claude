# Image & Asset Pipeline

How to handle images in any premium website without asking the user to do anything technical. Three modes:

1. **User has photos** → run `scripts/webp_convert.py` to convert to WebP automatically.
2. **User wants stock images** → run `scripts/openverse_fetch.py` to download from Openverse.
3. **Mix** → both, with credits properly attributed.

The user **never installs anything manually**. The Python scripts handle their own dependencies (Pillow auto-install with fallback).

---

## 1. The pipeline overview

```
[User photos OR Openverse]
         ↓
   assets/photos/source/      (originals — kept for re-runs, ignored at deploy)
         ↓
   webp_convert.py            (Pillow → WebP, sizes per category)
         ↓
   assets/img/                (final WebP, what HTML/CSS reference)
         ↓
   credits.json               (attribution metadata for credits page)
```

---

## 2. When to use Openverse vs ask the user

### Use Openverse silently when:

- The user said "I don't have photos" or didn't mention photos.
- The brief is for a generic / aspirational site (boutique hotel, agency, magazine) that doesn't have unique visuals.
- The user said "use stock" / "use whatever you find".
- The website needs >6 images and the user only provided 1–2.

### Ask the user for photos when:

- The brief is restaurant / product / portfolio — the photos ARE the product.
- The user mentioned having Instagram / Drive / Dropbox with photos.
- The site is hyper-personal (wedding planner, personal brand).
- They mentioned a specific product or location only they can photograph.

### How to ask (one short message)

> "Para que la web tenga el aspecto que toca, necesito 8 fotos: hero panorámica + 6 cuadradas o portrait + logo. Sube lo que tengas a la carpeta `{project}/assets/photos/source/` y aviso. Si prefieres que use imágenes de stock, dímelo y tiro de Openverse."

If they don't reply or say "stock" → default to Openverse.

---

## 3. Openverse fetch (no API key needed)

Openverse is the public API of the Wikimedia Foundation. **No registration, no API key, no rate limit auth.** Returns Creative Commons / public domain images from Wikimedia Commons, Flickr, Smithsonian, etc.

API: `https://api.openverse.org/v1/images/`

### Query design

The skill builds queries based on the project's industry + brand vocabulary:

```python
# In the skill's runtime, you generate this list dynamically per project:
queries = [
    {"id": "hero", "query": "minimalist coffee shop interior", "aspect": "wide", "size": "large"},
    {"id": "product-1", "query": "espresso macro pour", "aspect": None, "size": "large"},
    {"id": "product-2", "query": "barista hands portafilter", "aspect": "tall", "size": "large"},
    # ... 6-8 total
]
```

### License filter

Filter to safely-reusable licenses:
- `cc0` — public domain
- `pdm` — public domain mark
- `by` — attribution required
- `by-sa` — attribution + share-alike

**Do NOT** use `by-nc-*` (non-commercial) — your client website is commercial.

API param: `license=cc0,by,by-sa,pdm`.

### Renderable filter

Some results are `.tif` / `.svg` / huge files that browsers can't render normally. Filter:

```python
RENDERABLE = re.compile(r"\.(jpe?g|png|webp|gif|avif)(\?|$)", re.I)
```

### Size cap

API can return huge files (10–20 MB). Filter at fetch time and skip anything above 5 MB **unless** that's the only result.

### Attribution metadata

For each image, save:
```json
{
  "id": "hero",
  "src": "assets/img/hero.webp",
  "title": "Misty mountains",
  "creator": "John Doe",
  "creator_url": "https://flickr.com/people/...",
  "license": "by",
  "license_version": "2.0",
  "license_url": "https://creativecommons.org/licenses/by/2.0/",
  "foreign_landing_url": "https://flickr.com/photos/.../1234567890/",
  "source": "flickr"
}
```

This goes in `assets/credits.json`. The skill generates a `creditos.html` page with the full list, plus a small "Créditos fotográficos →" link in the footer.

### Compliance summary

- All images filtered by safe license types.
- Attribution page (`creditos.html`) auto-generated.
- Footer link to credits, small but visible (e.g., 12px text near copyright).
- For BY/BY-SA images: full attribution required (author + license + link).
- For CC0/PDM: attribution recommended, not required, but still listed for transparency.

---

## 4. WebP conversion

### Why WebP

- Universal modern browser support (Chrome, Edge, Firefox, Safari 14+).
- 30% smaller than JPEG at same quality.
- Single format → no `<picture>` mess, no fallback complications.

### Sizes per category

| Category | Max width | Quality | Target KB | Notes |
|---|---|---|---|---|
| Hero panoramic | 2000 px | 78 | <250 KB | preload with `<link rel="preload">` |
| Hero portrait | 1400 px | 80 | <200 KB | |
| Product / card full | 1100–1200 px | 80 | <200 KB | |
| Product / card thumb | 480–560 px | 75 | <50 KB | for galleries |
| Background ambient | 1600 px | 78 | <180 KB | hero alternatives |
| Logo / icon (alpha) | 600 px | 80 | <60 KB | preserve transparency |
| Avatar / portrait | 600 px | 78 | <80 KB | |

If a converted file exceeds the target, **reduce dimension** first, then quality. Going below quality 70 produces visible artifacts.

### Pillow vs FFmpeg

The script `webp_convert.py` uses **Pillow** (Python Imaging Library):
- Pure Python, `pip install pillow` (auto-handled by the script).
- Faster startup than ffmpeg.
- Native WebP support.

If Pillow can't install (no pip access, restricted environment), the script falls back to:
1. Looking for `ffmpeg` in PATH (some systems have it).
2. Looking for `cwebp` in PATH.
3. Last resort: copy files unchanged with a warning.

The skill should never block on this. If conversion fails, copy originals and warn the user once.

### Filename convention

```
hero.webp
hero-mobile.webp           # if a portrait alt is needed
product-tataki.webp        # category-name
thumb-product-tataki.webp  # corresponding thumb
local-bar.webp             # ambient
team-maria.webp            # portrait
logo.webp
```

Always kebab-case. Always categorize with prefix when there are multiple variations.

---

## 5. Hero image priority loading

```html
<head>
  <link rel="preload" as="image" href="assets/img/hero.webp" fetchpriority="high">
</head>
<body>
  <img src="assets/img/hero.webp" alt="..." fetchpriority="high" loading="eager" decoding="sync">
</body>
```

Other images:
```html
<img src="..." alt="..." loading="lazy" decoding="async">
```

---

## 6. Mobile alt-image (when portrait-vs-landscape matters)

```html
<picture>
  <source media="(max-width: 640px)" srcset="hero-mobile.webp">
  <img src="hero.webp" alt="...">
</picture>
```

Use sparingly. Only when a single hero image has framing issues on mobile.

---

## 7. Credits page (auto-generated)

The skill generates `creditos.html` with this template:

```html
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Créditos fotográficos · {Brand}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body class="page-credits">
  <header class="masthead">
    <a href="index.html">← Volver</a>
  </header>
  <main>
    <h1>Créditos fotográficos</h1>
    <p>Imágenes bajo licencias Creative Commons vía
       <a href="https://openverse.org" target="_blank" rel="noopener">Openverse</a>.</p>
    <ul class="credits-list" data-credits>
      <!-- Generated by JS from credits.json -->
    </ul>
  </main>
  <script defer src="lib/credits-render.js"></script>
</body>
</html>
```

`lib/credits-render.js` reads `assets/credits.json` via fetch and renders:

```js
fetch("assets/credits.json").then(r => r.json()).then(credits => {
  const list = document.querySelector("[data-credits]");
  list.innerHTML = Object.entries(credits).map(([id, c]) => `
    <li>
      <strong>${c.title}</strong> by
      ${c.creator_url ? `<a href="${c.creator_url}" target="_blank">${c.creator}</a>` : c.creator}
      (${c.source}) ·
      <a href="${c.license_url}" target="_blank">${c.license.toUpperCase()} ${c.license_version || ""}</a> ·
      <a href="${c.foreign_landing_url}" target="_blank">View original ↗</a>
    </li>
  `).join("");
});
```

Footer link from main pages:
```html
<p class="footer-credits">
  Imágenes bajo Creative Commons.
  <a href="creditos.html">Créditos fotográficos →</a>
</p>
```

Style it small but readable (~13px). The link must be **visible and present** in the footer for legal compliance.

---

## 8. User photos handling

### Folder structure

```
assets/photos/source/      ← user's originals (drag & drop here)
  hero.jpg
  plato-tataki.HEIC
  team-maria.png
  ...
```

### Auto-categorization heuristic

The conversion script asks (or assumes) the role of each file based on filename:
- `hero*` → hero treatment (large, 2000px, q78)
- `logo*` → alpha-preserved (600px, q80)
- `*-thumb*` → thumbnail (560px, q75)
- All others → standard product (1200px, q80)

If filenames are ambiguous, the script processes all as standard, and the skill reorganizes references in HTML/CSS based on what fits.

### .HEIC support

iPhone users upload `.heic` files. The script tries `pillow-heif`:

```python
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass  # .heic files will be skipped with a warning
```

If install fails, log: `WARNING: 3 .heic files skipped (install pillow-heif to support).`

---

## 9. Runtime fetch fallback (rare, only if local pipeline fails)

If for some reason images can't be downloaded ahead of time (e.g., disk write blocked), the skill can fetch from Openverse at runtime via `lib/openverse-runtime.js`:

```js
// Fallback only — used if assets/img is empty
async function loadImageFromOpenverse(query, slot) {
  const url = `https://api.openverse.org/v1/images/?q=${encodeURIComponent(query)}&license=cc0,by,by-sa,pdm&page_size=1`;
  const res = await fetch(url);
  const data = await res.json();
  if (data.results?.[0]) {
    slot.src = data.results[0].url;
    slot.alt = data.results[0].title;
  }
}
```

Use this only as a fallback. The default flow is always **fetch + WebP-convert at build time**.

---

## 10. Asset checklist before declaring done

- [ ] `assets/img/` contains WebP files only.
- [ ] No `.jpg` / `.png` / `.heic` in HTML/CSS/JS (except in scripts/, tools/, source/).
- [ ] Hero image preloaded with `<link rel="preload">`.
- [ ] All `<img>` have `alt` attribute (descriptive, not "image" or empty unless decorative).
- [ ] Decorative images have `aria-hidden="true"`.
- [ ] `loading="lazy"` on all non-hero images.
- [ ] `loading="eager" fetchpriority="high"` on hero.
- [ ] If using Openverse: `assets/credits.json` exists and `creditos.html` renders the list.
- [ ] If using Openverse: footer has visible "Créditos fotográficos" link.
- [ ] Total `assets/img/` size < 4 MB for the whole site.
- [ ] No image >250 KB except hero (which can be up to 250).

---

## 11. For non-WebP-supporting browsers (rare)

If you must support IE11 or very old Safari (rare in 2026):

```html
<picture>
  <source srcset="hero.webp" type="image/webp">
  <img src="hero.jpg" alt="...">     <!-- legacy fallback -->
</picture>
```

This means generating both formats, which doubles the asset folder. Only do this if the user explicitly says they need to support old browsers. **Default: WebP only.**

---

## 12. Common asset bugs (cross-reference)

- ❌ Mixed format references → grep before deploy (gotcha A.10).
- ❌ Hero loaded after content paints → use `<link rel="preload">` + `fetchpriority="high"`.
- ❌ Heavy images blocking first paint → all non-hero images `loading="lazy"`.
- ❌ Missing alt → fails accessibility checks.
- ❌ Credits page broken if `credits.json` is malformed → validate JSON in `verify_project.py`.
