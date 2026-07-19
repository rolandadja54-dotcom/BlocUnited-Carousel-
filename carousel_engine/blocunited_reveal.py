"""
BlocUnited // THE REVEAL  -  a "decryption" carousel engine
============================================================

A wholly different creative system from the news template. Every slide holds
the SAME headline in the SAME spot; one KEY phrase inside it stays redacted
behind a blue "decryption" bar. As the reader swipes, the bar recedes
left->right and uncovers the phrase one step at a time, while a "reveal meter"
climbs 0% -> 100%. The layout is intentionally identical slide-to-slide so the
deck reads as one continuous uncover - engineered to force swipe-through
completion (the metric Instagram rewards most).

Retains only the brand BLUE. Canvas is deep navy + blue.

Payload (rich form):
    {
      "kicker": "AI INTELLIGENCE", "handle": "@BlocUnited",
      "reveal": {"prefix": "The next leap in AI is",
                 "key": "AGENTS THAT SHIP CODE",
                 "suffix": "while your team sleeps."},
      "lead":  "cover intro line",
      "beats": ["slide-2 context", "slide-3 context", ...],
      "closing": "final payoff line",
      "share_prompt": "final share nudge"
    }
Total slides = 1 cover + len(beats) + 1 final.  reveal_frac = idx / (total-1).

A simple {"slides":[{"text":...}]} payload is also accepted: the engine
best-effort auto-picks a KEY token (a number / all-caps run, else the last
word) and treats the remaining slide texts as beats.

Public entry point:  render_deck(payload, out_dir, logo_path=None) -> [paths]
"""

from __future__ import annotations

import os
import re
import random
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Reuse the verified palette / fonts / low-level helpers from the first engine
# (kept in the repo for exactly this - shared brand tokens, no duplication).
from blocunited_carousel import (
    W, H, MARGIN,
    INK, INK_DEEP, PANEL, BRAND, SIGNAL, WHITE, MUTE, HAIRLINE,
    F_DISPLAY, F_COND, F_BODY, F_BODY_SL, F_MONO, F_MONO_B,
    font, _lerp, vgradient, valpha, add_grain,
    wrap, text_len, draw_tracked, tracked_len, place_logo, paint_base,
)

# --------------------------------------------------------------------------- #
#  LAYOUT CONSTANTS  (fixed so the reveal reads as one continuous frame)       #
# --------------------------------------------------------------------------- #

CONTENT_X = MARGIN
CONTENT_W = W - 2 * MARGIN

BLOCK_TOP = 300          # top of the (fixed) prefix/key/suffix reveal block
PREFIX_SIZE = 46
SUFFIX_SIZE = 46
KEY_SIZE_HI = 150
KEY_SIZE_LO = 60
BEAT_SIZE = 42


# --------------------------------------------------------------------------- #
#  TOP BAR  -  kicker (left)  +  reveal meter (right)                          #
# --------------------------------------------------------------------------- #

def draw_topbar(draw: ImageDraw.ImageDraw, ctx: dict, frac: float) -> None:
    y = MARGIN
    # --- kicker, left ---
    draw.rounded_rectangle([CONTENT_X, y + 6, CONTENT_X + 34, y + 14],
                           radius=3, fill=SIGNAL)
    kf = font(F_COND, 30)
    draw_tracked(draw, (CONTENT_X + 48, y - 4), ctx.get("kicker", "AI INTELLIGENCE").upper(),
                 kf, MUTE, tracking=3)

    # --- reveal meter, right ---
    pct = int(round(frac * 100))
    label = "DECODED" if frac >= 1.0 else "DECRYPTING"
    mf = font(F_MONO_B, 24)
    lf = font(F_MONO, 22)
    pct_s = f"{pct:d}%"
    lw = text_len(mf, pct_s) + 10 + text_len(lf, label)
    lx = W - MARGIN - lw
    draw.text((lx, y - 6), pct_s, font=mf, fill=SIGNAL if frac < 1 else WHITE)
    draw.text((lx + text_len(mf, pct_s) + 10, y - 4), label, font=lf, fill=MUTE)

    # track under the label
    track_w = 300
    tx0, tx1 = W - MARGIN - track_w, W - MARGIN
    ty = y + 34
    th = 12
    draw.rounded_rectangle([tx0, ty, tx1, ty + th], radius=6, fill=HAIRLINE)
    fillw = int(track_w * frac)
    if fillw > 0:
        draw.rounded_rectangle([tx0, ty, tx0 + max(fillw, th), ty + th],
                               radius=6, fill=SIGNAL)
    # tick marks per slide so the reader sees discrete "unlocks"
    total = ctx["total"]
    for i in range(total):
        mxp = tx0 + int(track_w * (i / max(1, total - 1)))
        col = WHITE if (i / max(1, total - 1)) <= frac + 1e-6 else HAIRLINE
        draw.line([(mxp, ty - 4), (mxp, ty + th + 4)], fill=col, width=2)


# --------------------------------------------------------------------------- #
#  DECRYPTION BAR  -  the blue redaction block that recedes across the deck    #
# --------------------------------------------------------------------------- #

def _decrypt_bar(w: int, h: int, seed: int = 0) -> Image.Image:
    """A fully-opaque blue 'encrypted' block: gradient + scanlines + data ticks."""
    w, h = max(1, w), max(1, h)
    layer = vgradient((w, h), _lerp(BRAND, SIGNAL, 0.18),
                      _lerp(BRAND, INK, 0.40)).convert("RGBA")
    d = ImageDraw.Draw(layer)
    # horizontal scanlines
    for yy in range(0, h, 4):
        d.line([(0, yy), (w, yy)], fill=(*INK_DEEP, 90), width=1)
    # deterministic bright "data" flecks so it reads as live decryption
    rnd = random.Random(seed)
    for _ in range(max(4, w // 24)):
        xx = rnd.randint(0, max(0, w - 8))
        yy = rnd.randint(0, max(0, h - 3))
        col = rnd.choice([SIGNAL, WHITE, _lerp(SIGNAL, WHITE, 0.5)])
        d.rectangle([xx, yy, xx + rnd.randint(3, 11), yy + 2], fill=(*col, 150))
    # left edge highlight = the "cut" where decryption is happening
    d.line([(0, 0), (0, h)], fill=(*SIGNAL, 220), width=2)
    return layer


def _decode_head(img: Image.Image, x: int, y0: int, y1: int) -> None:
    """Bright glowing vertical cap at the decryption boundary."""
    gw = 44
    halo = Image.new("RGBA", (gw * 2, y1 - y0), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    hd.rectangle([gw - 3, 0, gw + 3, y1 - y0], fill=(*SIGNAL, 130))
    halo = halo.filter(ImageFilter.GaussianBlur(7))
    img.alpha_composite(halo, dest=(int(x) - gw, y0))
    core = ImageDraw.Draw(img)
    core.line([(x, y0), (x, y1)], fill=(*WHITE, 255), width=3)
    # little caret pointing right (the direction of reveal)
    cy = (y0 + y1) // 2
    core.line([(x, cy - 12), (x + 12, cy)], fill=SIGNAL, width=3)
    core.line([(x, cy + 12), (x + 12, cy)], fill=SIGNAL, width=3)


# --------------------------------------------------------------------------- #
#  REVEAL BLOCK  -  prefix / KEY / suffix, identical position every slide      #
# --------------------------------------------------------------------------- #

def build_layout(deck: dict) -> dict:
    """Precompute fonts/positions ONCE so the block is pixel-identical per slide."""
    prefix = deck["prefix"].strip()
    key = deck["key"].strip()
    suffix = deck["suffix"].strip()

    pf = font(F_BODY, PREFIX_SIZE)
    sf = font(F_BODY, SUFFIX_SIZE)
    prefix_lines = wrap(prefix, pf, CONTENT_W) if prefix else []
    suffix_lines = wrap(suffix, sf, CONTENT_W) if suffix else []
    plh = int(PREFIX_SIZE * 1.2)
    slh = int(SUFFIX_SIZE * 1.2)

    # KEY must stay on a single line so the recede reads cleanly -> shrink to fit.
    ks = KEY_SIZE_HI
    while ks > KEY_SIZE_LO and text_len(font(F_DISPLAY, ks), key) > CONTENT_W:
        ks -= 2
    kf = font(F_DISPLAY, ks)
    kbb = kf.getbbox(key)            # (l, t, r, b) ink box at origin
    key_w = kf.getlength(key)
    key_ink_top, key_ink_bot = kbb[1], kbb[3]

    prefix_y = BLOCK_TOP
    prefix_h = len(prefix_lines) * plh
    key_y = prefix_y + prefix_h + (28 if prefix_lines else 0)
    key_h = key_ink_bot - key_ink_top
    suffix_y = key_y + key_h + 40
    suffix_h = len(suffix_lines) * slh
    beat_y = suffix_y + suffix_h + 66

    return {
        "prefix_lines": prefix_lines, "pf": pf, "plh": plh, "prefix_y": prefix_y,
        "key": key, "kf": kf, "key_w": key_w, "key_y": key_y,
        "key_top": key_y + key_ink_top - 8, "key_bot": key_y + key_ink_bot + 8,
        "suffix_lines": suffix_lines, "sf": sf, "slh": slh, "suffix_y": suffix_y,
        "beat_y": beat_y, "seed": deck["seed"],
    }


def draw_reveal_block(img: Image.Image, L: dict, frac: float) -> None:
    draw = ImageDraw.Draw(img)
    # prefix
    y = L["prefix_y"]
    for ln in L["prefix_lines"]:
        draw.text((CONTENT_X, y), ln, font=L["pf"], fill=_lerp(WHITE, MUTE, 0.10))
        y += L["plh"]

    # KEY (drawn in bright blue; then redaction bar hides the un-revealed tail)
    kx, ky = CONTENT_X, L["key_y"]
    draw.text((kx, ky), L["key"], font=L["kf"], fill=SIGNAL)

    key_w = L["key_w"]
    reveal_x = kx + key_w * frac
    top, bot = L["key_top"], L["key_bot"]
    if frac < 1.0 - 1e-6:
        bx0 = int(reveal_x)
        bx1 = int(kx + key_w) + 10          # small overhang past the last glyph
        bar = _decrypt_bar(bx1 - bx0, bot - top, seed=L["seed"] + int(frac * 100))
        img.alpha_composite(bar, dest=(bx0, top))
        _decode_head(img, reveal_x, top, bot)
    # faint baseline under the key so it feels seated even when fully revealed
    draw.line([(kx, bot + 4), (kx + int(key_w), bot + 4)],
              fill=_lerp(HAIRLINE, SIGNAL, 0.25), width=2)

    # suffix
    y = L["suffix_y"]
    for ln in L["suffix_lines"]:
        draw.text((CONTENT_X, y), ln, font=L["sf"], fill=WHITE)
        y += L["slh"]


# --------------------------------------------------------------------------- #
#  BOTTOM FURNITURE  -  swipe cue  /  final CTA                                #
# --------------------------------------------------------------------------- #

def draw_beat(draw: ImageDraw.ImageDraw, L: dict, text: str) -> None:
    if not text:
        return
    bf = font(F_BODY_SL, BEAT_SIZE)
    # accent tick to anchor the running context line
    y = L["beat_y"]
    draw.rounded_rectangle([CONTENT_X, y + 6, CONTENT_X + 8, y + 46],
                           radius=4, fill=BRAND)
    x = CONTENT_X + 26
    for ln in wrap(text, bf, CONTENT_W - 26)[:5]:
        draw.text((x, y), ln, font=bf, fill=_lerp(WHITE, MUTE, 0.16))
        y += int(BEAT_SIZE * 1.28)


def draw_swipe_cue(draw: ImageDraw.ImageDraw) -> None:
    f = font(F_MONO_B, 26)
    s = "SWIPE TO REVEAL"
    y = H - 168
    x = CONTENT_X
    draw.text((x, y), s, font=f, fill=MUTE)
    ax = x + text_len(f, s) + 18
    ay = y + 14
    draw.line([(ax, ay), (ax + 26, ay)], fill=SIGNAL, width=4)
    draw.line([(ax + 16, ay - 8), (ax + 26, ay)], fill=SIGNAL, width=4)
    draw.line([(ax + 16, ay + 8), (ax + 26, ay)], fill=SIGNAL, width=4)


def draw_final_cta(img: Image.Image, ctx: dict) -> None:
    """Share prompt + DYNAMIC-WIDTH follow pill, anchored ABOVE the logo slot."""
    draw = ImageDraw.Draw(img)
    handle = ctx.get("handle", "@BlocUnited")
    prompt = ctx.get("share_prompt", "Send this to someone who needs to see it.")

    pill_h = 86
    py = H - 210 - pill_h                 # pill sits clear of the bottom logo slot

    # share prompt stacked directly above the pill
    pf = font(F_BODY_SL, 40)
    plines = wrap(prompt, pf, CONTENT_W)[:3]
    y = py - 26 - len(plines) * 50
    for ln in plines:
        draw.text((CONTENT_X, y), ln, font=pf, fill=_lerp(WHITE, MUTE, 0.08))
        y += 50

    # DYNAMIC-WIDTH follow pill (fixed-width clipped the handle in the old engine)
    ff = font(F_COND, 50)
    ftxt = f"FOLLOW  {handle}"
    fb = ff.getbbox(ftxt)
    pill_w = (fb[2] - fb[0]) + 88
    draw.rounded_rectangle([CONTENT_X, py, CONTENT_X + pill_w, py + pill_h],
                           radius=pill_h // 2, fill=SIGNAL)
    draw.text((CONTENT_X + 44, py + (pill_h - (fb[3] - fb[1])) / 2 - fb[1]),
              ftxt, font=ff, fill=INK)


# --------------------------------------------------------------------------- #
#  SLIDE RENDER                                                                #
# --------------------------------------------------------------------------- #

def render_slide(idx: int, ctx: dict, L: dict) -> Image.Image:
    total = ctx["total"]
    frac = idx / max(1, total - 1)
    is_cover = idx == 0
    is_final = idx == total - 1

    variant = "gradient" if (is_cover or is_final) else "solid"
    img = paint_base(variant, L["seed"] + idx).convert("RGBA")

    draw = ImageDraw.Draw(img)
    draw_topbar(draw, ctx, frac)
    draw_reveal_block(img, L, frac)

    beat = ctx["contexts"][idx]
    draw = ImageDraw.Draw(img)   # refresh after alpha_composite in reveal block
    draw_beat(draw, L, beat)

    if is_final:
        draw_final_cta(img, ctx)
    else:
        draw_swipe_cue(draw)

    place_logo(img, draw, ctx.get("logo_path"))
    return img


# --------------------------------------------------------------------------- #
#  PAYLOAD NORMALISATION                                                       #
# --------------------------------------------------------------------------- #

_KEY_NUM_RE = re.compile(r"\$?\d[\d,\.]*\s?(?:%|x|×|hours?|hrs?|days?|B|M|K|bn|\+)?", re.I)
_CAPS_RE = re.compile(r"\b(?:[A-Z][A-Za-z0-9]*\s?){1,3}\b")


def _auto_key(text: str) -> tuple[str, str, str]:
    """Best-effort prefix / KEY / suffix from a flat sentence."""
    t = (text or "").strip().rstrip(".")
    if not t:
        return "", "THE SHIFT", ""
    m = _KEY_NUM_RE.search(t)                 # prefer a leading number/stat
    if not m or len(m.group(0)) < 2:
        # fall back to the last 2-3 words
        words = t.split()
        k = words[-2:] if len(words) > 3 else words[-1:]
        key = " ".join(k)
        prefix = " ".join(words[: len(words) - len(k)])
        return prefix, key.upper(), ""
    key = m.group(0).strip()
    return t[: m.start()].strip(), key.upper(), t[m.end():].strip()


def normalize(payload: dict) -> dict:
    """Return a flat deck spec: prefix/key/suffix + contexts[] (one per slide)."""
    kicker = payload.get("kicker", "AI INTELLIGENCE")
    handle = payload.get("handle", "@BlocUnited")

    if "reveal" in payload:
        rv = payload["reveal"]
        prefix, key, suffix = rv.get("prefix", ""), rv.get("key", ""), rv.get("suffix", "")
        beats = list(payload.get("beats", []))
        lead = payload.get("lead", "Swipe — we decode this one layer at a time.")
        closing = payload.get("closing", "Now you see the whole picture.")
        share = payload.get("share_prompt", "Send this to someone who needs to see it.")
    else:
        raw = payload.get("slides", [])
        texts = [(s.get("text") or "").strip() for s in raw if (s.get("text") or "").strip()]
        head = payload.get("headline") or (texts[0] if texts else "")
        prefix, key, suffix = _auto_key(head)
        beats = texts[1:-1] if len(texts) > 2 else texts[1:]
        lead = texts[0] if texts else "Swipe to reveal."
        closing = texts[-1] if len(texts) > 1 else "Now you see it."
        share = payload.get("share_prompt", "Send this to someone who needs to see it.")

    contexts = [lead] + beats + [closing]      # len == total
    total = len(contexts)
    seed = abs(hash(key + str(total))) % 997

    return {
        "kicker": kicker, "handle": handle, "share_prompt": share,
        "prefix": prefix, "key": key, "suffix": suffix,
        "contexts": contexts, "total": total, "seed": seed,
    }


# --------------------------------------------------------------------------- #
#  ORCHESTRATOR                                                                #
# --------------------------------------------------------------------------- #

def render_deck(payload: dict, out_dir: str, logo_path: Optional[str] = None) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    deck = normalize(payload)
    L = build_layout(deck)

    ctx = {
        "total": deck["total"],
        "kicker": deck["kicker"],
        "handle": deck["handle"],
        "share_prompt": deck["share_prompt"],
        "contexts": deck["contexts"],
        "logo_path": logo_path or payload.get("logo_path"),
    }

    paths = []
    for i in range(deck["total"]):
        img = render_slide(i, ctx, L).convert("RGB")
        p = os.path.join(out_dir, f"slide_{i + 1:02d}.png")
        img.save(p, "PNG", optimize=True)
        paths.append(p)
    return paths
