# Deployment & Cache strategy

The single biggest source of post-launch confusion: **the developer uploads new code and the bug is still there**. It's almost always cache. This document explains how to make every deploy reliably fresh, on Hostinger and equivalents.

---

## 1. The cache problem in one paragraph

Hostinger / shared Apache hosts / CDNs (Cloudflare in front of any host) serve static files (`.css`, `.js`, `.webp`) with `Cache-Control: max-age=2592000` (30 days) or longer by default. Browsers cache locally for the same period. The CDN caches at edge nodes for hours-to-days. **Uploading a new file does NOT invalidate any of these caches.** The user reloads, sees the old version, complains "it's still broken".

Solving cache requires a 3-layer strategy:
1. **Server side** — `.htaccess` tells the host's Apache: don't cache HTML/JS/CSS aggressively.
2. **HTML side** — cache-busting query strings (`?v=YYYYMMDD`) on every script/style reference.
3. **Source side** — avoid ES modules with relative imports, because their internal `import` chains don't carry the cache-buster.

All three are mandatory. Skip any one and the bug returns.

---

## 2. Layer 1 — `.htaccess` template

Every project ships with a `.htaccess` at the project root. The skill copies it from `templates/htaccess.template` automatically.

**Minimum content:**

```apache
# HTML: never cache
<IfModule mod_expires.c>
  ExpiresActive On
  ExpiresByType text/html "access plus 0 seconds"
  ExpiresByType text/css "access plus 1 hours"
  ExpiresByType application/javascript "access plus 1 hours"
  ExpiresByType application/json "access plus 1 hours"
  ExpiresByType image/webp "access plus 1 month"
  ExpiresByType image/jpeg "access plus 1 month"
  ExpiresByType image/png "access plus 1 month"
  ExpiresByType image/svg+xml "access plus 1 month"
  ExpiresByType font/woff2 "access plus 1 month"
</IfModule>

<IfModule mod_headers.c>
  <FilesMatch "\.(html|css|js|mjs|json)$">
    Header set Cache-Control "no-cache, must-revalidate"
  </FilesMatch>
  <FilesMatch "\.(webp|jpg|jpeg|png|svg|woff|woff2)$">
    Header set Cache-Control "public, max-age=2592000"
  </FilesMatch>
</IfModule>

<IfModule mod_mime.c>
  AddType image/webp .webp
  AddType application/javascript .js
  AddType application/javascript .mjs
  AddType text/css .css
</IfModule>
```

**What it does:**
- HTML: clients revalidate **every** visit. New deploy is visible immediately.
- JS / CSS / JSON: revalidate every visit. The server can still respond `304 Not Modified` if the file hasn't changed (saves bandwidth) but if it changed, serves the new version.
- Images and fonts: cached for 1 month (these change rarely; if they do change, rename the file or version it).
- MIME types: ensures Hostinger serves `.webp` and `.js` correctly (some shared hosts don't recognize `.webp` by default → broken images).

**Notes:**
- Works on Apache (Hostinger default).
- Works on LiteSpeed (Hostinger uses it on some plans) — both `mod_expires` and `mod_headers` are supported.
- **Doesn't work on Nginx** without manual server config. If the user is on Nginx, document this as a manual step.
- **Doesn't work for static-only hosts** like Netlify or Cloudflare Pages — those have their own header config (`netlify.toml`, `_headers` file). Document as needed.

---

## 3. Layer 2 — Cache-busting query strings in HTML

Even with perfect server headers, the user's browser may have an old version cached locally that "expires next month". A query-string change is treated by browsers and CDNs as **a new URL**, forcing a fresh download.

**On every deploy, bump the version:**

```html
<link rel="stylesheet" href="styles.css?v=20260511" />
<script defer src="main.js?v=20260511"></script>
```

Strategy:
- Use date format `YYYYMMDD`: human-readable, monotonically increasing, no risk of collision.
- Bump on **every** deploy that changes JS or CSS. If only HTML changed, no bump needed.
- All HTML files in the project share the same version string for that deploy.

**For multi-page sites:** every HTML file (`index.html`, `kyoto.html`, `creditos.html`, etc.) needs the same `?v=` value bumped consistently. Easy to forget. The skill should generate a single source of truth and inject the same value everywhere.

---

## 4. Layer 3 — Avoid ES modules with relative imports

ES modules (`<script type="module">`) have a fatal cache-busting weakness: the `?v=` on the `<script src>` does **not** propagate to the internal `import` chain. If `main.js?v=20260511` does:

```js
import { initEffects } from "./lib/effects.js";  // no version!
```

…the browser fetches `./lib/effects.js` without a cache buster. If the server / CDN caches that file, the user gets stale JS even though the entry-point looks fresh.

**Solution: use the IIFE pattern** (documented in `01-stack-and-conventions.md` §4). Classic `<script defer>` tags + `window.__BRAND__` namespace. No imports. Every script is an entry point that the HTML loads with its own cache-buster.

**Bonus benefit:** ES modules also fail on `file://` (CORS). If the client double-clicks `index.html` to preview, modules silently break. IIFEs work everywhere.

---

## 5. The deploy checklist (copy-paste for the assistant)

Before declaring "the website is ready":

- [ ] `.htaccess` is in the project root (copied from `templates/htaccess.template`).
- [ ] All `<link>` and `<script>` tags in HTML have `?v=YYYYMMDD` matching today's date.
- [ ] No `<script type="module">` anywhere (except possibly during dev, never in deliverable).
- [ ] No `import` / `export` keywords in any deliverable JS.
- [ ] All scripts use `<script defer>` + IIFE pattern.
- [ ] On every subsequent change to JS or CSS, bump the `?v=` value.

If the user reports "the bug is still there after upload":
1. **First step**: bump `?v=` and re-upload HTML files. 80% of cases solved.
2. **Second step**: ask them to open DevTools → Network → reload → check if `styles.css` and `main.js` show `200` (fresh) or `(disk cache)` (stale). If stale, the browser cache is winning over the server. Hard reload (Ctrl+Shift+R) or change the version string again.
3. **Third step**: verify the `.htaccess` reached Hostinger and is being applied. Open `https://their-site.com/.htaccess` directly — Hostinger should respond `403 Forbidden` (correct, the file exists but isn't web-accessible). If it responds `404`, the file wasn't uploaded.

---

## 6. Hostinger-specific notes

| Plan | Cache behavior | Notes |
|---|---|---|
| **Single / Premium / Business shared** | Apache + .htaccess works | Default behavior — works as documented |
| **Cloud** | LiteSpeed | `.htaccess` works, possibly with extra LSCache plugin |
| **VPS** | Nginx (config-dependent) | `.htaccess` is **ignored**. Must edit `nginx.conf` server block |

If the user is on a Nginx VPS (rare for our target), tell them: "Tu plan no usa `.htaccess`. Necesitamos configurar caché desde el panel de Hostinger o desde Nginx. Si quieres, lo guío paso a paso, pero como mitigación rápida, basta con bumpear `?v=` en cada deploy".

---

## 7. Alternative hosts (optional, if user mentions them)

### Netlify

Cache headers via `_headers` file at project root:

```
/*
  Cache-Control: no-cache, must-revalidate

/*.webp
  Cache-Control: public, max-age=2592000

/*.woff2
  Cache-Control: public, max-age=2592000
```

### Cloudflare Pages

Similar `_headers` file (Netlify-compatible syntax).

### GitHub Pages

No server config available. Rely entirely on cache-busting query strings (`?v=YYYYMMDD`).

### S3 + CloudFront

Set `Cache-Control` metadata on each object via AWS CLI:

```bash
aws s3 cp main.js s3://bucket/main.js --cache-control "no-cache, must-revalidate"
```

CloudFront also requires invalidation after deploy:
```bash
aws cloudfront create-invalidation --distribution-id ABCD --paths "/*"
```

---

## 8. The "I uploaded but still see the bug" diagnostic

When the user complains, ask three questions in order:

1. **"¿Qué URL tienes en la barra del navegador?"**
   - `file://...` → can't preview ES modules. Use a server.
   - `http://localhost:...` → check the server is pointing to the right folder.
   - `https://their-site.com/...` → it's Hostinger, continue with cache diagnostic.

2. **"Abre DevTools (F12) → pestaña Network → recarga (Ctrl+Shift+R) → busca `styles.css` y `main.js`. ¿Qué pone en la columna 'Status'?"**
   - `200` with size in KB → fresh download, code is updated. Bug must be elsewhere.
   - `200` `(from disk cache)` → browser cache. Try `Ctrl+Shift+R` again or open in incognito.
   - `304 Not Modified` → server says "no change since last download". If the user uploaded changes, the server is serving the wrong file. Re-upload or bump `?v=`.

3. **"¿Qué pone en el `Cache-Control` header (clic en el archivo, pestaña Headers, sección Response Headers)?"**
   - `no-cache, must-revalidate` → `.htaccess` working.
   - `max-age=2592000` or similar → `.htaccess` not applied. Re-upload `.htaccess` or check if hosting supports it.

These three questions diagnose 99% of cache-related complaints in under 2 minutes.
