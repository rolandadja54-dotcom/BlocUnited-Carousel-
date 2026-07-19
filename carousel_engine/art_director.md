# BlocUnited // AI Art Director — daily carousel brain

This is the contract for the LLM node that **brainstorms a fresh carousel every
day** instead of stamping a fixed template. It researches the day's top AI story,
writes the headline, and designs a *variable* deck: it chooses how many slides,
what TYPE each slide is, and which slides deserve a **fal.ai** image — writing the
image prompt itself. A renderer then overlays crisp text on the fal.ai art.

Retain only the brand **blue**; canvas is deep navy + blue.

---

## Pipeline (runs in n8n)

```
[Schedule] → [Research: LLM]         # find top AI story + headline
           → [Art Director: LLM]     # output the deck PLAN (JSON below)
           → [fal.ai: HTTP]  x N     # generate cover + per-slide images from prompts
           → [Render: Python engine] # overlay headline/body text, compose text slides
           → [Post / Save]           # 6–9 PNGs = the carousel
```

- **fal.ai** is the image generator (API key stored in n8n credentials).
  - Pure imagery / backgrounds → **Flux** (fast, photoreal).
  - A slide that truly needs *baked* legible text → **Recraft V3** or **Ideogram**.
- **Text is overlaid by the renderer**, never baked by the model for headlines —
  keeps every word legible and spelled right.

---

## The Art Director's job (LLM system prompt)

> You are the art director for **BlocUnited**, an AI-news brand. Each day you are
> given the top AI-space story. Design ONE Instagram carousel (4:5, 6–9 slides)
> that *expands* the story for a smart but busy reader.
>
> Rules:
> - Slide 1 is always a **cover** with a full-bleed generated photo + the headline.
> - The last slide is always a **cta** (follow + share prompt).
> - In between, **VARY the slide types** — do NOT repeat the same layout. Pick from
>   the catalog below based on what the story actually needs. Some days are
>   stat-heavy, some are quote/story-driven, some lean on imagery.
> - Add a generated image to a slide ONLY when it earns its place (a scene, a
>   product shot, a concept illustration). Write a vivid `image_prompt` for those.
> - ≤ 18 words per slide. One idea per slide. Big, punchy, plain language.
> - Keep a through-line: each slide should make the reader want the next.
> - Return ONLY the JSON plan in the schema below. No prose.

---

## Slide-type catalog (the Art Director picks per slide — not fixed)

| type            | purpose                                   | key fields |
|-----------------|-------------------------------------------|------------|
| `cover`         | slide 1 — hero photo + headline           | `headline`, `image_prompt` |
| `statement`     | one bold claim, text only                 | `body` |
| `stat`          | oversized number that lands the point     | `stat.value`, `stat.label` |
| `quote`         | pull-quote from a person/report           | `quote.text`, `quote.author` |
| `bullets`       | 2–4 short points expanding the story      | `items[]` |
| `image_caption` | a generated image + caption               | `image_prompt`, `body` |
| `comparison`    | before/after or A vs B                    | `items[2]` (each `{label, body}`) |
| `timeline`      | sequence of events / how it unfolds       | `items[]` (each `{label, body}`) |
| `explainer`     | "what this means for you" short paragraph | `title`, `body` |
| `cta`           | last slide — follow + share               | `body` (share prompt) |

Any slide MAY also set `image_prompt` + `image_role` to pull in fal.ai art.

---

## Output schema (what the LLM node returns)

```json
{
  "date": "2026-07-19",
  "topic": "coding agents",
  "headline": "AI AGENTS NOW SHIP CODE WHILE YOU SLEEP",
  "kicker": "AI INTELLIGENCE",
  "handle": "@BlocUnited",
  "cover_image_prompt": "cinematic dark navy server room at night, a single glowing blue terminal, volumetric light, ultra-detailed, editorial tech photography, 4:5",
  "sources": ["https://…"],
  "slides": [
    { "type": "cover", "headline": "AI AGENTS NOW SHIP CODE WHILE YOU SLEEP",
      "image_prompt": "…", "image_role": "full" },

    { "type": "statement",
      "body": "The debate moved on from chatbots. Agents now DO the work — end to end." },

    { "type": "stat",
      "stat": { "value": "30+ hrs", "label": "saved per week by early teams" } },

    { "type": "timeline", "title": "How one task now runs itself", "items": [
      { "label": "01", "body": "Reads the ticket and plans the fix." },
      { "label": "02", "body": "Writes the code and runs the tests." },
      { "label": "03", "body": "Opens the pull request for a human to review." }
    ] },

    { "type": "image_caption",
      "image_prompt": "over-the-shoulder shot of an engineer reviewing a glowing code diff on a dark screen, blue accent light, editorial, 4:5",
      "image_role": "background",
      "body": "The human moves up the stack: from typing code to reviewing decisions." },

    { "type": "quote",
      "quote": { "text": "The bottleneck is no longer writing code. It's describing the right problem.",
                 "author": "— a lead engineer, on the shift" } },

    { "type": "explainer", "title": "What this means for you",
      "body": "Learn to direct agents now. In 2026 the edge goes to the people who aim them, not the ones who resist them." },

    { "type": "cta",
      "body": "Know a founder still doing this by hand? Send them this." }
  ]
}
```

Notes for the renderer:
- `slides[0]` must be `cover`, `slides[-1]` must be `cta` (validate + coerce).
- Each `image_prompt` → one fal.ai call; result saved and passed to the renderer
  as `image_path` for that slide.
- `image_role`: `full` (bleed behind everything), `background` (dim, text over it),
  `inset` (framed image inside the slide).

---

## Build status
- [x] Art-director contract + slide-type catalog + JSON schema (this file)
- [ ] `fal_image.py` — fal.ai client (reads `FAL_KEY` env / n8n credential)
- [ ] Renderer refactor — one block per slide type, consumes the plan, overlays
      text on fal.ai imagery (replaces the fixed Reveal/News templates)
- [ ] `generate_deck.py` — runs a plan JSON → PNGs (demo with placeholder images)
