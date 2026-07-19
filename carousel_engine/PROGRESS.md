# BlocUnited Carousel Engine — Progress & Resume Notes

_Last updated: 2026-07-19_

## The goal
Build a **brand-new, standalone Python carousel engine** for BlocUnited — NOT edit
the existing n8n workflow. Research top brands' carousel styles, synthesize an
original creative system. **Retain ONLY the brand color blue.** Dark navy + blue canvas.

## Key decisions locked in
- ✅ Do NOT touch the existing `News Carousel Flow (Simplified).json` (untouched — only read once).
- ✅ New creativity — do NOT replicate the existing news template structure (cover→hook→body→CTA).
- ✅ Canvas: **dark navy + blue** (retain only blue).
- ✅ Chosen concept: **"B — The Reveal system"**
      Each slide keeps the SAME headline in the SAME spot; a blue "decryption"
      bar recedes as you swipe, uncovering the key phrase left-to-right. A
      "reveal meter" fills at the top. Built to force swipe-through completion.
- ⏳ OPEN QUESTION: content type for the carousel — still AI news/updates, or
      something else (tips / product / story)? Default = AI news (matches BlocUnited)
      unless the user redirects after seeing the first render.
- 🔲 Logo: user will provide the real logo AFTER the build → engine has a logo slot
      (`carousel_engine/assets/logo.png`). Used verbatim if present; placeholder wordmark otherwise.

## Research findings (2026 carousel engagement)
- Carousels = top format (~1.9% eng vs ~0.5% Reels); IG re-serves to non-swipers.
- DM shares weighted 3–5× higher than likes → final slide needs a share prompt.
- 8–10 slides win (current flow only makes 6).
- Seamless / "bleed" designs = ~40% higher completion → the Reveal mechanic leans on this.
- Micro-learning: 15–20 words/slide max, one idea, big type.
- Premium tech look = deep navy + ONE cool-blue accent used sparingly; oversized
  display numerals as anchors; mono meta tags.

## What exists so far (files in carousel_engine/)
- `blocunited_carousel.py` — FIRST direction engine (dark navy + blue, cover/hook/
  body/stat/cta). Works & renders, but this mirrors the OLD structure the user
  rejected. **Superseded by the Reveal concept** — keep for reference/helpers.
- `generate_carousel.py` — CLI runner for the above (`--demo`, `--input`, `--stdin`).
- `out/slide_01..06.png` — sample render of the first direction (looked premium).
- `assets/` — empty; drop real `logo.png` here later.
- Env verified: Python 3.14.3, Pillow 12.2.0. Fonts: arialbd, bahnschrift,
  segoeui/segoeuisl, consola/consolab (all at C:\Windows\Fonts).

## ✅ DONE (2026-07-19 session 2) — Reveal engine built & rendering
- `blocunited_reveal.py` + `generate_reveal.py` built. Imports shared brand
  tokens/helpers from `blocunited_carousel.py` (DRY, no duplication).
- Demo renders 8 slides to `out_reveal/`. Verified visually:
    - Slide 1 = 0% redacted, slide 4 = 43% mid-decrypt w/ glowing decode head,
      slide 8 = 100% revealed. The recede reads as ONE continuous uncover. ✅
    - "DECRYPTING → DECODED" reveal meter w/ per-slide unlock ticks. ✅
    - Key phrase auto-shrinks to one line; layout pixel-identical every slide. ✅
- Bugs from old engine carried over & FIXED here: dynamic-width FOLLOW pill
  (shows full "@BlocUnited"), final CTA anchored clear above the logo slot.
- Run:  `python generate_reveal.py --demo --out out_reveal`

## NEXT STEP (resume here)
0. NEW: get user sign-off on the rendered demo; then (a) confirm content type
   (default AI news), (b) drop real `assets/logo.png`, (c) optionally wire the
   engine to accept live payloads (n8n --stdin already supported).
   Possible polish: per-slide scanline sweep on the beat area, tune KEY size floor.

--- (historical resume notes below, now completed) ---
1. Build `blocunited_reveal.py` — the Reveal engine (new, self-contained).
   - Same navy+blue palette & helpers as blocunited_carousel.py (fonts, gradients,
     wrap, fit_block, place_logo).
   - Layout is CONSISTENT across slides so the reveal reads as one continuous uncover:
     - Top: kicker (left) + "reveal meter" mono bar (right), fills 0%→100%.
     - Middle: reveal block = prefix line(s, white) + KEY phrase line (big, blue,
       the redaction target) + suffix line(s, white). Same position every slide.
     - The KEY line has a blue "decryption" bar covering the un-revealed RIGHT
       portion: reveal_frac = idx/(N-1). Bar recedes left→right across slides.
       Add scanline texture + bright SIGNAL "decode head" cap at the boundary.
     - Below: per-slide beat text (story context), wrapped, semilight.
     - Bottom: logo slot; "SWIPE TO REVEAL →" on non-final; FOLLOW pill + share
       prompt on final slide.
   - Payload shape:
     {
       "kicker": "AI INTELLIGENCE", "handle": "@BlocUnited",
       "reveal": {"prefix": "...", "key": "30 HOURS", "suffix": "..."},
       "beats": ["slide 2 context", "slide 3 context", ...],
       "closing": "final payoff line", "share_prompt": "..."
     }
     Slides = 1 cover + len(beats) + 1 final. Also support fallback from simple
     {"slides":[{"text":...}]} with best-effort auto-key (number/caps token, else last word).
2. Build `generate_reveal.py` runner (--demo / --input / --stdin), rich demo payload.
3. Render demo, VIEW the PNGs, fix any rendering bugs.

## Known bugs to carry over (were mid-fix in blocunited_carousel.py, NOT critical
    since that direction is superseded — but apply the same care in the Reveal engine):
- CTA pill must be DYNAMIC width (fixed 520 clipped "@BlocUnited").
- Stat/number extraction must only fire when a number LEADS a slide, never
  mid-sentence (it broke "across 47 files" → "across files").
- Keep meta footer clear of the centered logo slot.

## How to run (once built)
    cd "C:\Users\HP\Desktop\BlocUnited Workflow\carousel_engine"
    python generate_reveal.py --demo --out out
    # then open out/slide_01.png ... to review
