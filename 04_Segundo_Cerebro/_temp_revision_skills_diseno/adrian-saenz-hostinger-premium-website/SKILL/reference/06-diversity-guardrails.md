# Diversity Guardrails — preventing copy-paste outputs

This skill is fed with three reference projects (Nómada, 911 Restaurante, The Gambit). Without explicit anti-monotony rules, you will end up generating webs that look like clones of those three. **Don't.**

The user has seen those three. They want their own. Diversity is part of the deliverable.

---

## 1. The rotation log

Before generating any project, **mentally check the last 3–5 archetypes used**. If the brief naturally points to one used recently, force the next-best alternative.

### Maintain awareness like this

When the user describes their brief:
1. Note the obvious archetype (e.g., "restaurant" → 02 Dark Warm).
2. Check: have I used 02 in any of my recent generations?
3. If yes → look at the alternative column in `02-archetypes.md`'s quick reference table. Use that instead.
4. If no good alternative exists → adapt the archetype heavily (different palette tone, different signature effects).

### Example rotation

| Recent | New brief | Default would be | Forced alternative |
|---|---|---|---|
| 02 Dark Warm (last project) | Wine bar | 02 Dark Warm | 03 3D Cinematic with sommelier theme |
| 01 Cream | Yoga retreat | 01 Cream (cream fits wellness) | 08 Liquid Wave (water/flow theme) |
| 05 Mouse Gradient | AI tool startup | 05 Mouse | 04 Glassmorphism |

---

## 2. Never copy these specific elements from reference projects

These elements are **strongly associated** with one of the references. If you use them, the user will recognize it. Avoid unless the new project genuinely demands them.

### From Nómada (don't repeat unless brief is identical)

- ❌ Bilingual scramble between original alphabet and Spanish.
- ❌ "Viajes de autor · Desde 2014" eyebrow style.
- ❌ The exact destination card layout (image + meta bottom).
- ❌ Search bar in hero with magnifying glass on the right.
- ❌ Cmd+K command palette for travel destinations.
- ❌ The 8-card asymmetric bento grid pattern (you can use bento, but with different proportions).

### From 911 Restaurante (don't repeat)

- ❌ Glyph signature 九一一 (kanji as decoration).
- ❌ "Cocina X-Y" italic split headline.
- ❌ Strip 3D rotating bilingual flip cards.
- ❌ Showcase scroll horizontal pinneado of 8–12 dishes.
- ❌ Mesh gradient red-warm specifically.
- ❌ Rating "4,7 ★ · 140 reseñas en Google" pattern.

### From The Gambit (don't repeat)

- ❌ Persistent Three.js scene of a chess board.
- ❌ Lookside camera split (subject left, text right pattern).
- ❌ Floating chess pieces decoration.
- ❌ "El boletín que juega contigo" italic style headline with metallic accent.
- ❌ Mate pastor narrative as scroll-driven story.

You can absolutely use **Three.js, scrambles, mesh gradients, horizontal scrolls, glyphs**. Just not the *exact same* deployment of them.

---

## 3. Diversification dimensions

When generating a new web, force differences in **multiple** dimensions:

### Dimension 1 — Palette family

| Family | Example tones |
|---|---|
| **Cream / paper** | `#f4efe6`, `#faf7f0` |
| **Dark warm** | `#0e0b09`, `#13100c` |
| **Dark deep cinematic** | `#050302`, `#0a0a14` |
| **Cool light pastel** | `#e0f7fa`, `#f5f0ea` |
| **Pure white + black** | `#fff`, `#000` |
| **Newspaper sepia** | `#faf7f0`, `#16140e` |
| **Iridescent dark** | `#0a0a14`, gradients magenta+cyan |
| **Mint + gold** | `#a8e6cf`, `#e7c878` |

If your last project used "cream", don't use cream again.

### Dimension 2 — Typography pairing

| Pairing | Mood |
|---|---|
| Fraunces (italic display) + Inter | Editorial warm |
| Cormorant + Söhne | Luxe minimal |
| Bodoni Moda + Source Serif | Newspaper classical |
| Playfair Display + Manrope | Tech-luxury |
| ABC Diatype Mono only | Brutalist mono |
| Helvetica Neue Condensed + Inter | Corporate confident |
| Italiana + GT Walsheim | Boutique feminine |
| EB Garamond + JetBrains Mono | Print-meets-tech |
| GT Sectra + Inter | Modern editorial |
| Migra italic + Söhne | Designer label |

Rotate. Don't use Fraunces in every project even if it's amazing.

### Dimension 3 — Hero topology

| Topology | Visual feel |
|---|---|
| Image + center-aligned italic display + CTA pair | Editorial classic |
| Full-bleed video loop + minimal text overlay | Cinematic |
| 3D scene + transparent overlay text | Tech / cinematic |
| Massive type filling viewport + tiny tagline below | Brutalist |
| Mesh gradient bg + product image floating + headline | Modern luxury |
| Two-column split (image left, text right) | Magazine |
| Image cutout overlapping text | Editorial dynamic |
| Pure typography no image | Confidence statement |
| Animated SVG illustration + headline | Friendly tech |
| Spline embed iframe + minimal text | Product-first |

### Dimension 4 — Grid composition

| Grid | Usage |
|---|---|
| Bento asymmetric (8 cards, different sizes) | Premium magazine |
| Strict 12-col with hairlines | Brutalist / architectural |
| Single column 60ch max | Long-form editorial |
| 3-column with column-rule | Newspaper |
| Horizontal scroll pinned | Showcase narrative |
| Free-floating cards on grid background | Glassmorphism |
| Vertical timeline | Process / history |
| Stacked panels with perspective | Storytelling |
| Mosaic of varying aspects | Gallery |
| Single panoramic with section dividers | Linear narrative |

### Dimension 5 — Signature interaction

Pick ONE that defines this project:

| Signature | Anchor archetype |
|---|---|
| Bilingual scramble | 01 |
| Strip 3D flip | 02 |
| Persistent 3D scene | 03 |
| Glassmorphism cards float | 04 |
| Mouse-reactive gradient | 05 |
| Reading progress + drop caps | 06 |
| Hover invert | 07 |
| Liquid wave dividers | 08 |
| Multi-column body text | 09 |
| Spline iframe rotation | 10 |

A web has ONE signature. Other effects support it.

---

## 4. Cross-archetype anti-mixing

Do **not** combine signature elements from different archetypes:

❌ Bento grid (01) + Mesh gradient warm (02) + Particles (03)
   → Confused identity. Pick one.

❌ Brutalist mono (07) + Glassmorphism (04)
   → They cancel each other.

❌ Liquid waves (08) + Newspaper (09)
   → Tone clash.

✅ Bento (01) + bilingual scramble (01) + Cmd+K (01) + custom cursor (01)
   → All archetype 01. Coherent.

---

## 5. Industry-driven defaults (with rotation)

The first time you encounter an industry, use the default. The next 1–2 times for similar industries, force the alternative.

```
Restaurant:      [02 Dark, 09 Newspaper, 01 Cream*]
                 *only for casual / brunch / boutique
Travel agency:   [01 Cream, 06 Magazine, 03 3D for adventure]
Newsletter:      [03 3D, 06 Magazine, 09 Newspaper]
SaaS:            [05 Mouse, 04 Glass, 10 Spline*]
                 *only if there's a hardware product
Studio:          [07 Brutalist, 03 3D, 05 Mouse]
Wellness:        [08 Liquid, 04 Glass, 01 Cream]
Coffee:          [01 Cream, 06 Magazine, 09 Newspaper]
```

If you've used 02 Dark for the last 2 restaurants, the next restaurant gets 09 Newspaper or 01 Cream.

---

## 6. Forbidden combinations (will look bad)

- Bento grid + multi-column newspaper layout (compete).
- Custom cursor + Cmd+K + side dot nav + scroll progress + hamburger (kitchen sink).
- Three.js scene + mesh gradient + particles + parallax (overkill).
- Italic serif + mono body (clash).
- Pure black `#000` + cream text (vibrating).
- Glassmorphism + dark editorial (genre clash).
- Marquee + horizontal pinned scroll + scroll-snap (scroll fighting).

---

## 7. Microcopy diversity

Even with similar archetype, microcopy must feel different:

### Eyebrows — never repeat the same template

- ❌ "Viajes de autor · Desde 2014" (too Nómada).
- ❌ "Cocina japo-mediterránea" (too 911).
- ❌ "Edition 042 · 2026" (too Gambit).

✅ Variety:
- "Cuaderno No. 47 · Marzo"
- "Una pequeña casa, en el centro"
- "Studio de diseño desde [year]"
- "Newsletter mensual · Issue 12"
- "Marca de [product] · Madrid"
- "Estudio fotográfico de autor"

### Headlines — different rhetorical patterns

Don't always use "X que Y" with italic emphasis. Mix:

- "Una pregunta [italic question]?"
- "[Number] formas de [action]."
- "[Adjective] como [metaphor]."
- "[Statement]. [Pause]. [Statement]."
- "[Verb] [object]. [Verb] [object]. [Verb] [object]."
- "[Single huge word]." (one word)
- "Lo que [action] cuando [condition]."

### CTAs — vary the ask

| Generic | Specific |
|---|---|
| "Empezar" | "Reservar mesa", "Apuntarse al boletín", "Pedir cita", "Hablar con nosotros", "Empieza tu viaje", "Conocer la carta" |

Always tie CTA wording to the user's actual ask.

---

## 8. Effect rotation tracker (mental log)

For your last 3 projects, mentally log:

| # | Industry | Archetype | Signature effect | Palette family | Hero topology |
|---|---|---|---|---|---|
| -1 | (last project) | | | | |
| -2 | | | | | |
| -3 | | | | | |

For project #0 (the new one), choose values that **don't appear** in the previous 3.

If the brief truly forces a repeat (e.g., another travel agency right after one), differentiate via:
- **Different country/cultural focus** (Spain vs Japan vs Iceland).
- **Different season tone** (warm summer vs cold winter palette).
- **Different age target** (young 25-35 vs senior travelers).
- **Different effect** (the previous used scramble; this one uses 3D).

---

## 9. The "would the user notice" test

Before declaring a project done, ask yourself:

> "If I show this to the same user who saw my last 3 projects, would they recognize a pattern?"

If yes → change something. Specifically:
- Different palette family.
- Different signature effect.
- Different hero topology.
- Different microcopy template.

Even small changes (a different signature effect) make outputs feel like distinct projects rather than variations of the same template.

---

## 10. Mandatory variations per category

When generating multiple projects in the same broad category (e.g., 5 different travel agencies for different clients), enforce these variations:

1. **At least 2 different archetypes** across the 5 projects.
2. **At least 3 different palette families**.
3. **No repeated signature effect**.
4. **Different hero topology** for each (no two identical heroes).
5. **Different navigation pattern** (sticky transparent vs centered logo vs side dock vs hamburger-only).

The user should be able to put all 5 outputs side by side and not see a "same studio" feel.

---

## 11. The temperature dial

For each project, consciously dial these on a 0–10 scale and aim for variation:

| Dial | 0 | 5 | 10 |
|---|---|---|---|
| **Brightness** | Pitch dark | Mid | Pure white |
| **Contrast** | Low (greyscale) | Moderate | Maximal |
| **Density** | Lots of whitespace | Balanced | Packed |
| **Curvature** | Sharp / brutalist | Mixed | All round/liquid |
| **Movement** | Static | Subtle | Constantly moving |
| **Type weight** | All thin 200 | Mix | All extra-bold |
| **Saturation** | Monochrome | Mid | Neon |

For each new project, change at least 3 dial values significantly compared to the last.

---

## 12. Implementation note for the skill

When invoked, the skill should internally:

1. Recall (from session memory or a notes file the user maintains) the last few projects.
2. Apply rotation rules.
3. Pick archetype + signature + palette + microcopy with diversity in mind.
4. Generate.

If the skill doesn't have access to history (fresh session), still apply diversity within the current project (don't pile every effect, pick one signature, etc.) — that handles the case when the user wants a single output.

For users who run the skill multiple times in a row, the rotation rules above prevent monotony.

---

## TL;DR — the 5 anti-monotony rules

1. **Pick ONE archetype** from the 10 in `02-archetypes.md`. Never combine.
2. **Don't reuse signature elements** from Nómada / 911 / Gambit.
3. **Rotate**: if the natural archetype was used recently, pick the alternative.
4. **One signature effect** per project. Other effects support, don't compete.
5. **Microcopy must feel different** even when the archetype matches.

If you respect these 5, every output will feel like a distinct, intentional project — not a variation of a template.
