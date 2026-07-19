"""
Research + Art Director (Python) for the BlocUnited carousel.
=============================================================

Fully in Python — mirrors the old n8n agents (Tavily research + OpenAI writing):
  1. Tavily  -> pulls recent AI-space news.
  2. OpenAI  -> picks the top story, writes the headline / summary / social caption,
                and DESIGNS a variable deck (chooses slide TYPES, writes fal.ai image
                prompts) as one JSON plan the renderer consumes.

Keys are read from the environment (never hardcoded):
    OPENAI_API_KEY, TAVILY_API_KEY, and optionally OPENAI_MODEL (default gpt-4o).

    from research import build_deck_plan
    plan = build_deck_plan()          # -> dict matching art_director.md schema

This module makes network calls; it needs live keys. The renderer runs fine
without it using a static plan (see main.py --plan / --demo).
"""

from __future__ import annotations

import json
import os
from typing import Optional

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
TAVILY_URL = "https://api.tavily.com/search"
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")


# The art director's brief. Each slide is a BUILDING BLOCK that advances the
# explanation; text stays short + legible; the deck varies its slide types.
ART_DIRECTOR_SYSTEM = """You are the art director AND writer for BlocUnited, an AI-news brand.
You are given the top AI-space story of the day. Design ONE Instagram carousel
(4:5 portrait, 7-9 slides) that fully EXPLAINS the story to a smart, busy reader.

Hard rules:
- Slide 1 is a `cover`: it carries the HEADLINE (rendered as text under an AI image)
  and its own `image_prompt` describing a cinematic, photoreal scene (NO text in the
  image — the headline is added separately).
- The last slide is a `cta` (follow + share prompt).
- BETWEEN them, VARY the slide types — never repeat the same layout twice in a row.
  Each slide is a BUILDING BLOCK: it adds one new idea that builds on the previous
  slide so that, by the end, the whole story is explained.
- Keep every slide short and LEGIBLE: <= 16 words, one idea, plain language.
- Add an `image_prompt` (+ `image_role`) to a middle slide ONLY when a picture truly
  helps (a scene, product shot, concept). Most slides are text-only on black.
- Image prompts must be vivid, cinematic, and contain NO text/words/letters.

Slide types you may use (pick per slide, based on the story):
  cover | statement | stat | quote | bullets | image_caption | comparison | timeline | explainer | cta
Field shapes:
  cover        -> {type, headline, image_prompt, image_role:"full"}
  statement    -> {type, body}
  stat         -> {type, stat:{value, label}}
  quote        -> {type, quote:{text, author}}
  bullets      -> {type, title?, items:[str,...]}          (2-4)
  image_caption-> {type, image_prompt, image_role:"background"|"inset", body}
  comparison   -> {type, title?, items:[{label, body},{label, body}]}
  timeline     -> {type, title?, items:[{label, body},...]} (2-4)
  explainer    -> {type, title, body}
  cta          -> {type, body}   (share prompt)

Return ONLY valid JSON in EXACTLY this shape (no markdown, no comments):
{
  "topic": "...",
  "headline": "SHORT PUNCHY HEADLINE (<= 8 words)",
  "summary": "2-3 sentence factual summary of the story",
  "caption": "the social post caption: hook + 2-3 lines + 3-5 hashtags",
  "kicker": "AI INTELLIGENCE",
  "handle": "@BlocUnited",
  "cover_image_prompt": "same as slides[0].image_prompt",
  "sources": ["url", "..."],
  "slides": [ {cover...}, ..., {cta...} ]
}
"""


def _require(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing env var {name} (needed for Python research).")
    return v


def tavily_search(query: str, max_results: int = 8, days: int = 3) -> list[dict]:
    import requests
    body = {
        "api_key": _require("TAVILY_API_KEY"),
        "query": query,
        "topic": "news",
        "search_depth": "advanced",
        "days": days,
        "max_results": max_results,
    }
    r = requests.post(TAVILY_URL, json=body, timeout=60)
    r.raise_for_status()
    return r.json().get("results", [])


def openai_json(system: str, user: str, model: str = DEFAULT_MODEL) -> dict:
    import requests
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
    }
    headers = {"Authorization": f"Bearer {_require('OPENAI_API_KEY')}",
               "Content-Type": "application/json"}
    r = requests.post(OPENAI_URL, json=body, headers=headers, timeout=120)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def build_deck_plan(query: str = "biggest AI news today: models, agents, funding, product launches",
                    model: str = DEFAULT_MODEL) -> dict:
    """Research the day's top AI story and return a full deck plan (dict)."""
    results = tavily_search(query)
    digest = "\n\n".join(
        f"- {r.get('title','')}\n  {r.get('url','')}\n  {r.get('content','')[:400]}"
        for r in results
    )
    user = (
        "Here are today's candidate AI-news items (from Tavily):\n\n"
        f"{digest}\n\n"
        "Pick the single most important / interesting story and design the carousel "
        "per your rules. Return only the JSON plan."
    )
    plan = openai_json(ART_DIRECTOR_SYSTEM, user, model=model)
    # keep cover_image_prompt in sync with the cover slide if the model omitted it
    slides = plan.get("slides", [])
    if slides and slides[0].get("image_prompt") and not plan.get("cover_image_prompt"):
        plan["cover_image_prompt"] = slides[0]["image_prompt"]
    return plan


if __name__ == "__main__":
    print(json.dumps(build_deck_plan(), indent=2))
