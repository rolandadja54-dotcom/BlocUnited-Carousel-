"""
Runner for the BlocUnited // THE REVEAL carousel engine.

    python generate_reveal.py --demo --out out
    python generate_reveal.py --input payload.json --out out
    echo '{...}' | python generate_reveal.py --stdin --out out

Drop a real logo at assets/logo.png (or pass --logo path) and it is used verbatim.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from blocunited_reveal import render_deck


DEMO_PAYLOAD = {
    "kicker": "AI INTELLIGENCE",
    "handle": "@BlocUnited",
    "reveal": {
        "prefix": "The next leap in AI isn't a chatbot. It's",
        "key": "AGENTS THAT SHIP CODE",
        "suffix": "while your team sleeps.",
    },
    "lead": "Everyone's arguing about chatbots. The real shift is quieter — "
            "and far bigger. Swipe to decode it.",
    "beats": [
        "Agentic AI now plans, calls tools, and executes multi-step tasks "
        "end-to-end — not just answering questions.",
        "It opens the ticket, writes the code, runs the tests, and files the "
        "pull request itself.",
        "The human moves up the stack: from typing code to reviewing decisions.",
        "Early teams report 30+ hours saved a week — a full extra engineer, "
        "for free.",
        "The bottleneck shifts. It's no longer writing code — it's describing "
        "the right problem clearly.",
        "And it compounds: every workflow you automate frees you to design "
        "the next one.",
    ],
    "closing": "2026 won't reward the people who resist this. It'll reward the "
               "ones who learn to direct it.",
    "share_prompt": "Know a founder still doing this by hand? Send them this.",
}


def main() -> None:
    ap = argparse.ArgumentParser(description="Render a BlocUnited REVEAL carousel.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--demo", action="store_true", help="render the built-in demo deck")
    src.add_argument("--input", metavar="FILE", help="path to a JSON payload")
    src.add_argument("--stdin", action="store_true", help="read JSON payload from stdin")
    ap.add_argument("--out", default="out", help="output directory (default: out)")
    ap.add_argument("--logo", default=None, help="path to logo (default: assets/logo.png if present)")
    args = ap.parse_args()

    if args.demo:
        payload = DEMO_PAYLOAD
    elif args.input:
        with open(args.input, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    else:
        payload = json.load(sys.stdin)

    here = os.path.dirname(os.path.abspath(__file__))
    logo = args.logo
    if logo is None:
        default_logo = os.path.join(here, "assets", "logo.png")
        logo = default_logo if os.path.exists(default_logo) else None

    paths = render_deck(payload, args.out, logo_path=logo)
    print(f"Rendered {len(paths)} slides -> {os.path.abspath(args.out)}")
    for p in paths:
        print("  " + os.path.basename(p))


if __name__ == "__main__":
    main()
