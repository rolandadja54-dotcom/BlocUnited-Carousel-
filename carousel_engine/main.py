"""
BlocUnited carousel — single Python entry point.
================================================

This is the ONE command n8n runs (Execute Command node). Everything creative is
Python; n8n only does the trigger, Google Drive hosting, and Blotato publishing.

Steps:
  1. Get a deck plan   (--research = Tavily+OpenAI in Python | --plan file | --demo)
  2. Generate images   (fal.ai for the cover + any slide image_prompts; --fal)
  3. Render the deck    (deck_render -> slide_01..N.png on black, image slides only)
  4. Write outputs      (slides + caption.txt + plan.json in --out)

n8n then: uploads each slide_*.png to Google Drive (folder "Frame"), builds the
download links, uploads them to Blotato /v2/media, aggregates the URLs, and posts
to every connected platform with caption.txt as the text.

Usage:
  python main.py --demo --out out_deck
  python main.py --research --fal --out out_deck        # full live run (needs keys)
  python main.py --plan plan.json --fal --out out_deck

Env (only for live runs): OPENAI_API_KEY, TAVILY_API_KEY, FAL_KEY, optional
OPENAI_MODEL / FAL_MODEL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from deck_render import render_deck
from generate_deck import DEMO_PLAN


def get_plan(args) -> dict:
    if args.research:
        from research import build_deck_plan          # imported lazily (needs keys)
        return build_deck_plan(query=args.query) if args.query else build_deck_plan()
    if args.plan:
        with open(args.plan, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return DEMO_PLAN


def build_caption(plan: dict) -> str:
    """The social post text Blotato posts (each platform appends its own CTA in n8n)."""
    cap = plan.get("caption")
    if cap:
        return cap
    # fall back to headline + a light nudge if the plan carried no caption
    head = plan.get("headline", "").strip()
    return f"{head}\n\nFollow @BlocUnited for daily AI intelligence."


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the BlocUnited carousel end to end.")
    ap.add_argument("--out", default="out_deck", help="output directory")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--research", action="store_true", help="research live via Tavily+OpenAI")
    src.add_argument("--plan", metavar="FILE", help="use an existing deck-plan JSON")
    src.add_argument("--demo", action="store_true", help="use the built-in demo plan (default)")
    ap.add_argument("--query", default=None, help="override the research query")
    ap.add_argument("--fal", action="store_true", help="generate real images via fal.ai")
    ap.add_argument("--logo", default=None, help="logo path (default assets/logo.png)")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    logo = args.logo
    if logo is None:
        default_logo = os.path.join(here, "assets", "logo.png")
        logo = default_logo if os.path.exists(default_logo) else None

    print("- getting deck plan ...")
    plan = get_plan(args)
    print(f"  headline: {plan.get('headline','(none)')}")
    print(f"  slides:   {len(plan.get('slides', []))}")

    os.makedirs(args.out, exist_ok=True)
    # persist the plan + caption so n8n (and you) can inspect / reuse them
    with open(os.path.join(args.out, "plan.json"), "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2, ensure_ascii=False)
    caption = build_caption(plan)
    with open(os.path.join(args.out, "caption.txt"), "w", encoding="utf-8") as fh:
        fh.write(caption)

    print(f"- rendering ({'fal.ai images' if args.fal else 'placeholder images'}) ...")
    paths = render_deck(plan, args.out, logo_path=logo, use_fal=args.fal)

    print(f"[ok] {len(paths)} slides -> {os.path.abspath(args.out)}")
    for p in paths:
        print("   " + os.path.basename(p))
    print("   caption.txt, plan.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
