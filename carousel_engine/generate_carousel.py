"""
CLI wrapper for the BlocUnited // SIGNAL carousel engine.

Usage
-----
  # From a news payload JSON (this is what n8n calls):
  python generate_carousel.py --input payload.json --out out --logo assets/logo.png

  # Read payload from stdin (handy for n8n Execute Command):
  cat payload.json | python generate_carousel.py --stdin --out out

  # See the style right now with built-in sample content:
  python generate_carousel.py --demo --out out

It prints a JSON line to stdout: {"slides":["out/slide_01.png", ...]}
so an n8n Code node can read the generated file paths directly.
"""

import os
import sys
import json
import argparse
import urllib.request

from blocunited_carousel import render_deck

HERE = os.path.dirname(os.path.abspath(__file__))

DEMO_PAYLOAD = {
    "kicker": "AI AGENTS",
    "handle": "@BlocUnited",
    "source": "Reuters",
    "date": "2026-07-19",
    "headline": "Anthropic's new agent runs your whole terminal for 30 hours straight",
    "share_prompt": "Know a founder still doing this by hand? Send them this.",
    "slides": [
        {"slide_number": 1,
         "text": "Anthropic just shipped an agent that codes for 30 hours unsupervised"},
        {"slide_number": 2,
         "text": "It did not just autocomplete. It shipped a working product overnight."},
        {"slide_number": 3,
         "text": "The agent planned, wrote, and tested code across 47 files.\n\nNo human touched the keyboard for the entire run."},
        {"slide_number": 4,
         "text": "Benchmarks jumped 18% on real engineering tasks.\n\nThat gap is what separates a demo from a coworker."},
        {"slide_number": 5,
         "text": "Solo builders can now ship like a five person team overnight."},
        {"slide_number": 6, "text": "Follow @BlocUnited for daily AI updates"},
    ],
}


def resolve_cover(payload, workdir):
    """If cover_image is a URL, download it next to the output."""
    ci = payload.get("cover_image")
    if ci and ci.lower().startswith(("http://", "https://")):
        dest = os.path.join(workdir, "_cover_src.png")
        try:
            urllib.request.urlretrieve(ci, dest)
            payload["cover_image"] = dest
        except Exception as e:
            sys.stderr.write(f"[warn] cover download failed: {e}\n")
            payload["cover_image"] = None
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="path to payload JSON")
    ap.add_argument("--stdin", action="store_true", help="read payload JSON from stdin")
    ap.add_argument("--demo", action="store_true", help="use built-in sample content")
    ap.add_argument("--out", default=os.path.join(HERE, "out"), help="output directory")
    ap.add_argument("--logo", default=os.path.join(HERE, "assets", "logo.png"),
                    help="path to logo PNG (used verbatim if present)")
    args = ap.parse_args()

    if args.demo:
        payload = DEMO_PAYLOAD
    elif args.stdin:
        payload = json.load(sys.stdin)
    elif args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            payload = json.load(f)
    else:
        ap.error("one of --demo, --stdin, or --input is required")

    os.makedirs(args.out, exist_ok=True)
    payload = resolve_cover(payload, args.out)

    logo = args.logo if os.path.exists(args.logo) else None
    paths = render_deck(payload, args.out, logo_path=logo)

    print(json.dumps({"slides": paths, "count": len(paths), "logo_used": bool(logo)}))


if __name__ == "__main__":
    main()
