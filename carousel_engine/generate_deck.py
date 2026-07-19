"""
Runner for the plan-driven BlocUnited carousel renderer.

    python generate_deck.py --demo --out out_deck          # placeholder images
    python generate_deck.py --input plan.json --out out_deck
    python generate_deck.py --input plan.json --fal --out out_deck   # real fal.ai
    cat plan.json | python generate_deck.py --stdin --out out_deck

The plan JSON is what the AI art director produces (see art_director.md).
Without --fal, every image slot is filled with a branded placeholder so you can
review layout today; with --fal it calls fal.ai (needs FAL_KEY in the env).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from deck_render import render_deck


# A worked "one day's deck" matching art_director.md — deliberately mixes slide
# types (cover · statement · stat · timeline · image_caption · quote · explainer · cta).
DEMO_PLAN = {
    "date": "2026-07-19",
    "topic": "coding agents",
    "headline": "AI AGENTS NOW SHIP CODE WHILE YOU SLEEP",
    "kicker": "AI INTELLIGENCE",
    "handle": "@BlocUnited",
    "cover_image_prompt": "cinematic dark navy server room at night, a single glowing "
                          "blue terminal screen, volumetric light, editorial tech "
                          "photography, ultra detailed, 4:5",
    "slides": [
        {"type": "cover", "headline": "AI AGENTS NOW SHIP CODE WHILE YOU SLEEP",
         "image_prompt": "cinematic dark navy server room at night, single glowing blue "
                         "terminal, volumetric light, editorial tech photography, 4:5",
         "image_role": "full"},

        {"type": "statement",
         "body": "The debate moved on from chatbots. Agents now DO the work — end to end.",
         "emphasis": ["do"]},

        {"type": "stat",
         "stat": {"value": "30+ hrs", "label": "saved every week by the earliest teams — a full extra engineer, for free."}},

        {"type": "timeline", "title": "How one task now runs itself", "items": [
            {"label": "1", "body": "Reads the ticket and plans the fix."},
            {"label": "2", "body": "Writes the code and runs the tests."},
            {"label": "3", "body": "Opens the pull request for a human to review."},
        ]},

        {"type": "image_caption",
         "image_prompt": "over-the-shoulder shot of an engineer reviewing a glowing blue "
                         "code diff on a dark screen, editorial, cinematic, 4:5",
         "image_role": "background",
         "body": "The human moves up the stack: from typing code to reviewing decisions."},

        {"type": "comparison", "title": "Where the bottleneck moved", "items": [
            {"label": "Before", "body": "Hours spent writing and debugging the code by hand."},
            {"label": "Now", "body": "Minutes spent describing the right problem clearly."},
        ]},

        {"type": "quote",
         "quote": {"text": "The bottleneck is no longer writing code. It's describing the right problem.",
                   "author": "— a lead engineer, on the shift"}},

        {"type": "explainer", "title": "What this means for you",
         "body": "Learn to direct agents now. In 2026 the edge goes to the people who aim "
                 "them — not the ones who resist them."},

        {"type": "cta",
         "body": "Know a founder still doing this by hand? Send them this."},
    ],
}


def main() -> None:
    ap = argparse.ArgumentParser(description="Render a BlocUnited carousel from a deck plan.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--demo", action="store_true", help="render the built-in demo plan")
    src.add_argument("--input", metavar="FILE", help="path to a deck-plan JSON")
    src.add_argument("--stdin", action="store_true", help="read the deck plan from stdin")
    ap.add_argument("--out", default="out_deck", help="output directory")
    ap.add_argument("--fal", action="store_true", help="generate images via fal.ai (needs FAL_KEY)")
    ap.add_argument("--logo", default=None, help="logo path (default: assets/logo.png if present)")
    args = ap.parse_args()

    if args.demo:
        plan = DEMO_PLAN
    elif args.input:
        with open(args.input, "r", encoding="utf-8") as fh:
            plan = json.load(fh)
    else:
        plan = json.load(sys.stdin)

    here = os.path.dirname(os.path.abspath(__file__))
    logo = args.logo
    if logo is None:
        default_logo = os.path.join(here, "assets", "logo.png")
        logo = default_logo if os.path.exists(default_logo) else None

    paths = render_deck(plan, args.out, logo_path=logo, use_fal=args.fal)
    mode = "fal.ai" if args.fal else "placeholder images"
    print(f"Rendered {len(paths)} slides ({mode}) -> {os.path.abspath(args.out)}")
    for p in paths:
        print("  " + os.path.basename(p))


if __name__ == "__main__":
    main()
