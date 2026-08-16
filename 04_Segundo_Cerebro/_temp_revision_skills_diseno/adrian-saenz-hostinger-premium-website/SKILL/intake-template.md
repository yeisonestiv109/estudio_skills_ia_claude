# User Intake — minimum questions to ask

After the user describes their project, ask the **minimum** number of follow-ups. Default behavior: decide silently.

## When to ask each question

| Question | Always ask? | When to skip |
|---|---|---|
| Brand name | Always (unless given) | If they said it |
| Photos: yours or stock? | Always | If they specified |
| Main CTA goal | Always (unless obvious) | If "subscribe" / "book table" / "buy" was clear |
| Pages: one or multi? | Sometimes | Default = one-page; ask only if their brief implies multi-page (menu + reservations, blog + archive, etc.) |
| Anything specific MUST include | Always (free-text optional) | — |

## Template message (Spanish — translate to user's language)

> Vale, antes de empezar:
> 1. **Nombre de la marca**: cómo se llama el proyecto.
> 2. **Fotos**: ¿tienes las tuyas o uso imágenes de stock con licencias libres? Si tienes, sube las fotos a `{project}/assets/photos/source/` cuando esté creada la carpeta.
> 3. **Objetivo principal**: ¿qué quieres que haga el visitante? (reservar, suscribirse, contactar, comprar, leer…).
> 4. **¿Algo concreto que la web tenga que incluir?** (ej. carta, blog, mapa, lista de servicios). Si no, paso al diseño.
> 5. **¿Una sola página o varias?** (Por defecto una sola.)
>
> Cuanto más concreto seas, mejor, pero responde rápido — el resto lo decido yo.

## DO NOT ASK

These are the skill's job to decide:
- Color palette → archetype + industry.
- Fonts → archetype.
- Layout → archetype.
- Effects → archetype's signature set.
- Tech decisions of any kind.
- "Do you want a custom cursor?" → no, you just include it if archetype says so.
- "Do you want a contact form?" → yes if they mentioned contact, no otherwise.

## After the user replies

Acknowledge in 1 line. Then go silent and execute. Do not narrate every step. Tell them when it's ready.

If they didn't reply / left ambiguity:
- Photos → default to Openverse stock.
- Pages → default to one-page.
- CTA → infer from industry (restaurant → reserve table; agency → contact; newsletter → subscribe).
- Anything else → use sensible default for the archetype.

## What to deliver at the end

One short message:
> Listo. La web está en `{project-folder}/`. Abre `index.html` para verla. Para subirla a Hostinger, arrastra toda la carpeta al File Manager.
>
> Si quieres tocar algo (copy, fotos, color, añadir páginas), dímelo.

Don't lecture about technical decisions. The user wants the result.
