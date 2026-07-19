# BlocUnited carousel — n8n integration (thin wrapper around Python)

Everything creative is Python. n8n only does: **trigger → run Python → Google Drive
hosting → Blotato publishing**. This keeps your existing Drive + Blotato logic.

## The 4 things n8n keeps (from `News Carousel Flow (Simplified).json`)
| Job | Old node(s) | Keep |
|-----|-------------|------|
| Trigger | `Schedule Daily2` | ✅ as-is |
| Host images | `Upload Carousel To Drive2` (Drive → *My Drive / folder "Frame"* `1kqE-p82pOgMttt7hKn6YoRhBxwZHNL0u`) | ✅ |
| Upload to Blotato | `Upload Media To Blotato2` → `POST https://backend.blotato.com/v2/media`, body `url = https://drive.google.com/uc?export=download&id={{ $json.id }}` | ✅ |
| Aggregate URLs | `Aggregate Media URLs2` (`url`) | ✅ |
| Publish | `POST /v2/posts` per platform — IG acct `9752`, FB acct `6649`/page `105432422174069`, X acct `4675`, LinkedIn **acct not set yet** | ✅ |

Everything else in the old flow (Tavily agent, GPT agents, `editImage` overlay,
fal HTTP polling, Telegram approvals) is REPLACED by the Python pipeline.

## New flow shape
```
Schedule Daily
  → Execute Command:  python main.py --research --fal --out /data/out_deck
  → Read caption:     Read File  /data/out_deck/caption.txt   (→ {{ $json.data }})
  → Read slides:      Read Files (glob) /data/out_deck/slide_*.png   (binary, sorted)
  → Google Drive:     Upload each slide  (folder "Frame")            [your node, in a loop]
  → Blotato media:    POST /v2/media  { url: drive download link }   [your node]
  → Aggregate:        collect `url` → array                          [your node]
  → Publish:          POST /v2/posts × {IG, FB, X, LinkedIn}         [your nodes]
```
Notes:
- Slide order matters → sort files by name (`slide_01 … slide_09`) before upload so
  the carousel reads in order.
- Point the Blotato post `text` at the caption file instead of `Set Story Fields2`:
  `"text": "{{ $('Read caption').first().json.data }}\n\n<platform CTA>"`.
- Keep each platform's extra CTA line exactly as you have it now.

## Env vars to set on the n8n host (NOT hardcoded in JSON)
```
OPENAI_API_KEY   = ...        # research + art director
TAVILY_API_KEY   = ...        # news search
FAL_KEY          = ...        # image generation
OPENAI_MODEL     = gpt-4o     # optional
FAL_MODEL        = flux       # or nano-banana-pro to match your old cover
```
Your self-hosted n8n already runs Python (like FaithVids), so `Execute Command`
works. Put `carousel_engine/` on the host and `pip install pillow requests`.

## ⚠️ Rotate the keys that were in plaintext in the OLD flow JSON
- The Blotato key (was in every publish node of the old flow)
- The fal.ai key (was in the old flow's cover nodes)
Move them to n8n **credentials / env** and generate new ones.

## What Python produces in `--out`
```
slide_01.png … slide_0N.png   the carousel (black bg; images only where placed)
caption.txt                    the social post text  → Blotato `text`
plan.json                      the full deck plan (for inspection / re-render)
```

## Local test commands
```
python main.py --demo  --out out_deck                 # no keys, placeholder images
python main.py --plan plan.json --fal --out out_deck  # real images from a saved plan
python main.py --research --fal --out out_deck         # full live run
```
