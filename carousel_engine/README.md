# BlocUnited Carousel Engine

Fully-Python daily AI-news carousel generator for BlocUnited. An AI art director
researches the day's top AI story, writes the headline + caption, designs a
*variable* deck (no fixed template), generates imagery with **fal.ai**, and
composes the finished slides. n8n only handles the **trigger, Telegram approval,
Google Drive hosting, and Blotato publishing**.

## What runs where
- **Python (this repo):** research → deck plan → images → rendered `slide_*.png` + `caption.txt`
- **n8n:** schedule → run this → preview/approve in Telegram → Drive → Blotato → socials

## VPS setup (Hostinger / self-hosted n8n)
```bash
# clone this repo to where the n8n Execute Command node expects it
git clone <this-repo-url> /data/carousel_engine
cd /data/carousel_engine
pip install -r requirements.txt

# set keys in the environment (do NOT hardcode them)
export OPENAI_API_KEY=...      # research + writing
export TAVILY_API_KEY=...      # news search
export FAL_KEY=...             # image generation
# optional: OPENAI_MODEL=gpt-4o   FAL_MODEL=flux (or nano-banana-pro)

# smoke test (placeholder images, no keys needed):
python main.py --demo --out out_deck
# full live run:
python main.py --research --fal --out out_deck
```
The n8n `Execute Command` node runs:
`cd /data/carousel_engine && python main.py --research --fal --out /data/out_deck`

## Outputs (in `--out`)
- `slide_01.png … slide_0N.png` — the carousel (black bg; images only where placed)
- `caption.txt` — the social caption Blotato posts
- `plan.json` — the full deck plan (for inspection / re-render)

## Key files
| File | Role |
|------|------|
| `main.py` | single entry point (research → images → render → outputs) |
| `research.py` | Tavily + OpenAI → deck plan (the art director) |
| `fal_image.py` | fal.ai queue-API image client (key from env) |
| `deck_render.py` | plan-driven renderer, one block per slide type |
| `blocunited_carousel.py` | shared brand tokens / helpers (imported by the renderer) |
| `art_director.md` | the art-director contract + slide-type catalog |
| `INTEGRATION.md` | how the n8n wrapper maps to this |
| `n8n/BlocUnited Carousel (Python).json` | the importable n8n workflow (no secrets) |

## Security
No secrets live in this repo — every key is read from the environment. Keep it a
**private** repository. Rotate any keys that were exposed in the old n8n JSON.
