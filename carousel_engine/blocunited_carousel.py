"""
BlocUnited // SIGNAL  -  creative carousel engine
==================================================

A content-driven Instagram carousel generator. It does NOT stamp a fixed
template: each slide is *composed* at render time - type is auto-fitted to its
box, layouts vary per slide, key words are highlighted, and a continuous
"signal rail" advances across the deck so swiping feels seamless.

Design language (synthesised from top tech / editorial brands):
  - Deep-navy authority canvas + ONE cool-blue accent used sparingly
  - Oversized ghost numerals that anchor the eye on each slide
  - Mono meta tags (source / date / index) - fits an AI-news brand
  - A left "signal rail" whose node advances 1..N as the reader swipes
  - A logo slot bottom-centre (drop assets/logo.png and it is used verbatim)

Public entry point:  render_deck(payload: dict, out_dir, logo_path=None) -> [paths]

The engine is deliberately count-agnostic: give it 6 slides or 10, it adapts.
"""

from __future__ import annotations

import os
import re
import math
import random
from dataclasses import dataclass, field
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

# --------------------------------------------------------------------------- #
#  CANVAS + BRAND TOKENS                                                       #
# --------------------------------------------------------------------------- #

W, H = 1080, 1350            # Instagram 4:5 portrait
MARGIN = 96
RAIL_X = 54                  # left signal-rail x position

# 4-role colour system (bg / text / accent / secondary) + support tones
INK      = (11, 15, 24)      # near-black navy  (#0B0F18)  - primary background
INK_DEEP = (7, 10, 17)       # darker tone for gradients / vignette
PANEL    = (18, 25, 40)      # raised panel / blue-tinted block
BRAND    = (64, 93, 160)     # BlocUnited blue  (#405DA0)  - inherited from flow
SIGNAL   = (92, 146, 250)    # brighter accent  (#5C92FA)  - highlights / node
WHITE    = (244, 247, 252)   # primary text
MUTE     = (139, 150, 170)   # secondary text / meta
HAIRLINE = (37, 47, 68)      # dividers / inactive rail

# Windows font stack (verified present on this machine)
_FDIR = r"C:\Windows\Fonts"
F_DISPLAY = os.path.join(_FDIR, "arialbd.ttf")     # headlines (bold grotesque)
F_COND    = os.path.join(_FDIR, "bahnschrift.ttf") # kickers / numerals (condensed)
F_BODY    = os.path.join(_FDIR, "segoeui.ttf")     # body copy
F_BODY_SL = os.path.join(_FDIR, "segoeuisl.ttf")   # body copy (semilight)
F_MONO    = os.path.join(_FDIR, "consola.ttf")     # meta tags
F_MONO_B  = os.path.join(_FDIR, "consolab.ttf")    # bold meta

_FONT_CACHE: dict = {}


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    key = (path, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(path, size)
    return _FONT_CACHE[key]


# --------------------------------------------------------------------------- #
#  LOW-LEVEL DRAW HELPERS                                                      #
# --------------------------------------------------------------------------- #

def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def vgradient(size, top, bottom):
    """Vertical gradient as an RGB image (cheap: build 1px column then stretch)."""
    w, h = size
    strip = Image.new("RGB", (1, h))
    px = strip.load()
    for y in range(h):
        px[0, y] = _lerp(top, bottom, y / max(1, h - 1))
    return strip.resize((w, h))


def valpha(size, top_a, bottom_a):
    """Vertical alpha mask ('L') - top_a at top, bottom_a at bottom."""
    w, h = size
    strip = Image.new("L", (1, h))
    px = strip.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = int(round(top_a + (bottom_a - top_a) * t))
    return strip.resize((w, h))


def add_grain(img, amount=7, seed=0):
    """Subtle film grain so flat navy never looks dead. Deterministic per deck."""
    rnd = random.Random(seed)
    noise = Image.new("L", (W // 2, H // 2))
    noise.putdata([128 + rnd.randint(-amount, amount) for _ in range(noise.width * noise.height)])
    noise = noise.resize((W, H)).filter(ImageFilter.GaussianBlur(0.4))
    overlay = Image.merge("RGB", (noise, noise, noise))
    return Image.blend(img, overlay, 0.05)


def text_len(f, s):
    return f.getlength(s)


def wrap(text, f, max_w):
    """Greedy word wrap. Honours explicit newlines already split by caller."""
    words = text.split()
    lines, cur = [], ""
    for wd in words:
        trial = wd if not cur else cur + " " + wd
        if text_len(f, trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def fit_block(text, font_path, box_w, box_h, size_hi, size_lo,
              line_gap=1.16, max_lines=99):
    """
    Largest font size at which `text` wraps inside (box_w, box_h) within
    max_lines. Returns (font, lines, line_height, total_h).
    This auto-fit is what makes the engine adaptive instead of templated.
    """
    for size in range(size_hi, size_lo - 1, -2):
        f = font(font_path, size)
        lines = wrap(text, f, box_w)
        lh = int(size * line_gap)
        total = lh * len(lines)
        widest = max((text_len(f, ln) for ln in lines), default=0)
        if len(lines) <= max_lines and total <= box_h and widest <= box_w:
            return f, lines, lh, total
    f = font(font_path, size_lo)
    lines = wrap(text, f, box_w)
    lh = int(size_lo * line_gap)
    return f, lines, lh, lh * len(lines)


# key-word emphasis: numbers / money / % / multipliers + caller-supplied words
_NUM_RE = re.compile(r"^\$?\d[\d,\.]*(?:%|x|×|B|M|K|bn|m|k|\+)?$", re.I)


def _emph_word(raw, emphasis_set):
    clean = raw.strip(".,;:!?\"'()[]").lower()
    return clean in emphasis_set or bool(_NUM_RE.match(raw.strip(".,;:!?\"'()[]")))


def draw_emph_lines(draw, lines, f, x, y, lh, base_col, accent_col,
                    emphasis_set, align="left", box_w=None, stroke=0):
    """Draw wrapped lines, colouring emphasised tokens in accent_col."""
    for ln in lines:
        if align in ("center", "right") and box_w is not None:
            lw = text_len(f, ln)
            cx = x + (box_w - lw) if align == "right" else x + (box_w - lw) / 2
        else:
            cx = x
        for tok in ln.split(" "):
            col = accent_col if _emph_word(tok, emphasis_set) else base_col
            draw.text((cx, y), tok, font=f, fill=col,
                      stroke_width=stroke, stroke_fill=col)
            cx += text_len(f, tok + " ")
        y += lh
    return y


def draw_tracked(draw, pos, s, f, fill, tracking=0):
    """Draw a short string with letter-spacing (used for kickers)."""
    x, y = pos
    for ch in s:
        draw.text((x, y), ch, font=f, fill=fill)
        x += text_len(f, ch) + tracking
    return x


def tracked_len(f, s, tracking=0):
    return sum(text_len(f, ch) + tracking for ch in s) - (tracking if s else 0)


# --------------------------------------------------------------------------- #
#  SHARED SLIDE FURNITURE                                                      #
# --------------------------------------------------------------------------- #

def paint_base(variant, seed):
    """Background canvas. Variants keep the deck cohesive but not identical."""
    if variant == "gradient":
        img = vgradient((W, H), INK, INK_DEEP)
    elif variant == "panel":
        img = vgradient((W, H), _lerp(INK, PANEL, 0.5), INK_DEEP)
    else:  # solid ink with faint top glow
        img = Image.new("RGB", (W, H), INK)
        glow = Image.new("RGB", (W, H), BRAND)
        mask = valpha((W, H), 46, 0)
        img = Image.composite(glow, img, mask)
    # corner vignette for depth
    vg = Image.new("RGB", (W, H), INK_DEEP)
    vmask = valpha((W, H), 0, 120)
    img = Image.composite(vg, img, vmask)
    return add_grain(img, seed=seed)


def signal_rail(draw, idx, total):
    """Vertical rail on the left; the glowing node advances 1..N across swipes."""
    y0, y1 = 150, H - 150
    draw.line([(RAIL_X, y0), (RAIL_X, y1)], fill=HAIRLINE, width=4)
    prog = (idx + 1) / total
    node_y = int(y0 + (y1 - y0) * prog)
    draw.line([(RAIL_X, y0), (RAIL_X, node_y)], fill=BRAND, width=4)
    # glow node
    for r, a in ((22, 40), (14, 90)):
        halo = Image.new("RGBA", (r * 2 + 2, r * 2 + 2), (0, 0, 0, 0))
        ImageDraw.Draw(halo).ellipse([0, 0, r * 2, r * 2], fill=(*SIGNAL, a))
        draw._image.paste(halo, (RAIL_X - r - 1, node_y - r - 1), halo)
    draw.ellipse([RAIL_X - 8, node_y - 8, RAIL_X + 8, node_y + 8], fill=SIGNAL)


def kicker(draw, label, y=MARGIN):
    """Top eyebrow: accent tick + tracked, uppercase category label."""
    draw.rounded_rectangle([MARGIN, y + 4, MARGIN + 34, y + 12], radius=3, fill=SIGNAL)
    f = font(F_COND, 30)
    draw_tracked(draw, (MARGIN + 48, y - 6), label.upper(), f, MUTE, tracking=3)


def index_tag(draw, idx, total):
    f = font(F_MONO_B, 30)
    s = f"{idx + 1:02d}"
    tot = f"/{total:02d}"
    x = W - MARGIN - text_len(font(F_MONO, 30), tot) - text_len(f, s)
    draw.text((x, MARGIN - 8), s, font=f, fill=WHITE)
    draw.text((x + text_len(f, s), MARGIN - 8), tot, font=font(F_MONO, 30), fill=MUTE)


def ghost_number(img, n):
    """Oversized low-opacity numeral behind body content - the visual anchor."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(F_COND, 620)
    s = str(n)
    bb = d.textbbox((0, 0), s, font=f)
    w = bb[2] - bb[0]
    d.text((W - w - 40 - bb[0], H - 760 - bb[1]), s, font=f, fill=(*BRAND, 34))
    img.alpha_composite(layer) if img.mode == "RGBA" else img.paste(
        Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB"), (0, 0))
    return img


def place_logo(img, draw, logo_path, y=None):
    """
    Logo slot, bottom-centre. If assets/logo.png exists it is used verbatim;
    otherwise a clearly-marked wordmark placeholder is drawn so the pipeline
    runs today. Drop your real logo in later and it is picked up automatically.
    """
    y = y if y is not None else H - 132
    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        target_w = 210
        ratio = target_w / logo.width
        logo = logo.resize((target_w, int(logo.height * ratio)))
        img.paste(logo, ((W - logo.width) // 2, y - logo.height // 2), logo)
        return
    # ---- placeholder wordmark (monogram tile + type) ----
    tile = 46
    word_f = font(F_COND, 40)
    label = "BLOCUNITED"
    lw = tracked_len(word_f, label, 2)
    total_w = tile + 16 + lw
    x0 = (W - total_w) // 2
    draw.rounded_rectangle([x0, y - tile // 2, x0 + tile, y + tile // 2],
                           radius=12, fill=BRAND)
    mf = font(F_DISPLAY, 30)
    mb = draw.textbbox((0, 0), "BU", font=mf)
    draw.text((x0 + (tile - (mb[2] - mb[0])) / 2 - mb[0],
               y - (mb[3] - mb[1]) / 2 - mb[1]), "BU", font=mf, fill=WHITE)
    draw_tracked(draw, (x0 + tile + 16, y - 20), label, word_f, WHITE, tracking=2)
    # tiny "logo slot" hint under placeholder
    hf = font(F_MONO, 16)
    hint = "logo slot"
    draw.text(((W - text_len(hf, hint)) / 2, y + 30), hint, font=hf, fill=HAIRLINE)


def swipe_hint(draw):
    f = font(F_MONO_B, 26)
    s = "SWIPE"
    x = W - MARGIN - text_len(f, s) - 44
    yb = H - 150
    draw.text((x, yb), s, font=f, fill=MUTE)
    ax = W - MARGIN - 34
    draw.line([(ax, yb + 16), (ax + 22, yb + 16)], fill=SIGNAL, width=4)
    draw.line([(ax + 14, yb + 8), (ax + 22, yb + 16)], fill=SIGNAL, width=4)
    draw.line([(ax + 14, yb + 24), (ax + 22, yb + 16)], fill=SIGNAL, width=4)


# --------------------------------------------------------------------------- #
#  SLIDE ARCHETYPES                                                            #
# --------------------------------------------------------------------------- #

CONTENT_X = MARGIN + 20      # indent past the rail
CONTENT_W = W - CONTENT_X - MARGIN


def render_cover(slide, ctx):
    idx, total = ctx["idx"], ctx["total"]
    seed = ctx["seed"]
    cover_img = ctx.get("cover_image")

    if cover_img and os.path.exists(cover_img):
        base = Image.new("RGB", (W, H), INK)
        photo = ImageOps.fit(Image.open(cover_img).convert("RGB"),
                             (W, int(H * 0.66)), centering=(0.5, 0.4))
        base.paste(photo, (0, 0))
        # scrim: photo fades into ink for the headline zone
        scrim = Image.new("RGB", (W, H), INK)
        base = Image.composite(scrim, base, valpha((W, H), 30, 255).point(
            lambda a: 0 if a < 150 else min(255, (a - 150) * 4)))
        # simpler robust scrim on bottom third
        grad = Image.new("RGB", (W, H), INK)
        m = valpha((W, H), 0, 255)
        base = Image.composite(grad, base, m.point(lambda a: 0 if a < 120 else (a - 120) * 2))
        img = base
    else:
        img = paint_base("gradient", seed)
        # faint brand mark motif behind type
        img = ghost_number(img.convert("RGBA"), (idx + 1)).convert("RGB") \
            if False else img

    draw = ImageDraw.Draw(img)
    signal_rail(draw, idx, total)
    kicker(draw, ctx.get("kicker", "AI INTELLIGENCE"))
    index_tag(draw, idx, total)

    headline = slide.get("headline", slide.get("text", "")).strip().upper()
    emphasis = set(w.lower() for w in slide.get("emphasis", []))
    box_top = int(H * 0.60)
    f, lines, lh, total_h = fit_block(headline, F_DISPLAY, CONTENT_W,
                                      H - box_top - 210, 118, 60,
                                      line_gap=1.02, max_lines=5)
    y = H - 200 - total_h
    draw_emph_lines(draw, lines, f, CONTENT_X, y, lh, WHITE, SIGNAL,
                    emphasis, align="left", box_w=CONTENT_W)

    place_logo(img, draw, ctx.get("logo_path"))
    swipe_hint(draw)
    return img


def render_hook(slide, ctx):
    idx, total, seed = ctx["idx"], ctx["total"], ctx["seed"]
    img = paint_base("solid", seed)
    draw = ImageDraw.Draw(img)
    signal_rail(draw, idx, total)
    kicker(draw, ctx.get("kicker", "THE HOOK"))
    index_tag(draw, idx, total)

    text = slide.get("text", slide.get("headline", "")).strip()
    emphasis = set(w.lower() for w in slide.get("emphasis", []))
    f, lines, lh, total_h = fit_block(text, F_DISPLAY, CONTENT_W, 620, 96, 54,
                                      line_gap=1.12, max_lines=6)
    y = (H - total_h) // 2 - 40
    # leading quote-mark accent
    qf = font(F_COND, 150)
    draw.text((CONTENT_X - 6, y - 130), "“", font=qf, fill=(*BRAND, 255))
    draw_emph_lines(draw, lines, f, CONTENT_X, y, lh, WHITE, SIGNAL,
                    emphasis, align="left", box_w=CONTENT_W)
    place_logo(img, draw, ctx.get("logo_path"))
    return img


def render_body(slide, ctx):
    idx, total, seed = ctx["idx"], ctx["total"], ctx["seed"]
    # per-slide deterministic variation so no two body slides feel identical
    variants = ["solid", "gradient", "panel"]
    variant = variants[(idx + seed) % len(variants)]
    show_ghost = (idx % 2 == 0)

    img = paint_base(variant, seed + idx).convert("RGBA")
    if show_ghost:
        img = ghost_number(img, idx + 1)
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    signal_rail(draw, idx, total)
    kicker(draw, ctx.get("kicker", "BREAKDOWN"))
    index_tag(draw, idx, total)

    headline = slide.get("headline", "").strip()
    body = slide.get("body", slide.get("text", "")).strip()
    emphasis = set(w.lower() for w in slide.get("emphasis", []))

    # stat detection: a short line dominated by a number -> hero-numeral layout
    stat = _detect_stat(body if not headline else body)
    y = 260

    if stat and len(body) < 120:
        big_f = font(F_COND, 300)
        draw.text((CONTENT_X - 8, y), stat["num"], font=big_f, fill=SIGNAL)
        y += 300
        rest_f = font(F_BODY, 44)
        for ln in wrap(stat["rest"], rest_f, CONTENT_W):
            draw.text((CONTENT_X, y), ln, font=rest_f, fill=WHITE)
            y += 56
    else:
        if headline:
            hf, hlines, hlh, hh = fit_block(headline, F_DISPLAY, CONTENT_W, 300,
                                            72, 44, line_gap=1.06, max_lines=4)
            y = draw_emph_lines(draw, hlines, hf, CONTENT_X, y, hlh, WHITE,
                                SIGNAL, emphasis, box_w=CONTENT_W)
            draw.line([(CONTENT_X, y + 18), (CONTENT_X + 70, y + 18)],
                      fill=SIGNAL, width=5)
            y += 52
        # body: honour explicit paragraph breaks
        paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        bf = font(F_BODY_SL, 46)
        for p in paras:
            for ln in wrap(p, bf, CONTENT_W):
                draw.text((CONTENT_X, y), ln, font=bf, fill=_lerp(WHITE, MUTE, 0.12))
                y += 60
            y += 26

    _meta_footer(draw, ctx)
    place_logo(img, draw, ctx.get("logo_path"))
    return img


def render_cta(slide, ctx):
    idx, total, seed = ctx["idx"], ctx["total"], ctx["seed"]
    img = vgradient((W, H), _lerp(INK, BRAND, 0.20), INK_DEEP)
    img = add_grain(img, seed=seed)
    draw = ImageDraw.Draw(img)
    signal_rail(draw, idx, total)
    kicker(draw, "YOUR MOVE")
    index_tag(draw, idx, total)

    handle = ctx.get("handle", "@BlocUnited")
    # share prompt (drives DM shares - weighted 3-5x by the algorithm)
    prompt = slide.get("share_prompt", "Know a founder who needs this? Send it their way.")
    hf, hlines, hlh, hh = fit_block(prompt, F_DISPLAY, CONTENT_W, 520, 84, 48,
                                    line_gap=1.1, max_lines=6)
    y = 300
    y = draw_emph_lines(draw, hlines, hf, CONTENT_X, y, hlh, WHITE, SIGNAL,
                        set(), box_w=CONTENT_W)
    y += 40
    ff = font(F_COND, 52)
    draw.rounded_rectangle([CONTENT_X, y, CONTENT_X + 520, y + 88],
                           radius=44, fill=SIGNAL)
    ftxt = f"FOLLOW  {handle}"
    fb = draw.textbbox((0, 0), ftxt, font=ff)
    draw.text((CONTENT_X + 40, y + (88 - (fb[3] - fb[1])) / 2 - fb[1]),
              ftxt, font=ff, fill=INK)

    place_logo(img, draw, ctx.get("logo_path"))
    return img


# --------------------------------------------------------------------------- #
#  CONTENT NORMALISATION  (news payload -> typed slides)                       #
# --------------------------------------------------------------------------- #

_STAT_RE = re.compile(r"(\$?\d[\d,\.]*\s?(?:%|x|×|billion|million|B|M|K|bn)?)", re.I)


def _detect_stat(text):
    m = _STAT_RE.search(text or "")
    if not m:
        return None
    num = m.group(1).strip()
    if len(num) > 12:
        return None
    rest = (text[:m.start()] + text[m.end():]).strip(" ,.:;")
    return {"num": num, "rest": rest} if rest else None


def _meta_footer(draw, ctx):
    src, date = ctx.get("source", ""), ctx.get("date", "")
    if not (src or date):
        return
    y = H - 176
    draw.line([(CONTENT_X, y), (W - MARGIN, y)], fill=HAIRLINE, width=2)
    f = font(F_MONO, 24)
    tag = "  ·  ".join([t for t in (src.upper(), date) if t])
    draw.text((CONTENT_X, y + 16), tag, font=f, fill=MUTE)


_ROLE_RENDERERS = {
    "cover": render_cover,
    "hook": render_hook,
    "body": render_body,
    "cta": render_cta,
}


def normalize(payload: dict) -> list[dict]:
    """
    Accepts either
      A) rich:  {"slides":[{"role":"cover","headline":...}, ...]}
      B) n8n:   {"slides":[{"slide_number":1,"text":"..."}], "headline":..,"summary":..}
    and returns a list of typed slide dicts with an assigned `role`.
    """
    raw = payload.get("slides", [])
    n = len(raw)
    out = []
    for i, s in enumerate(raw):
        # already typed?
        if "role" in s:
            out.append(dict(s))
            continue
        text = (s.get("text") or "").strip()
        # infer role from position + content
        if i == 0:
            role = "cover"
        elif re.match(r"(?i)^\s*follow\b", text) or i == n - 1:
            role = "cta"
        elif i == 1:
            role = "hook"
        else:
            role = "body"
        slide = {"role": role, "text": text}
        if role == "cover":
            slide["headline"] = text or payload.get("headline", "")
        if role == "cta":
            # keep a share prompt distinct from the raw "Follow @..." line
            slide["share_prompt"] = payload.get(
                "share_prompt", "Save this. Share it with a builder who ships.")
        out.append(slide)
    return out


# --------------------------------------------------------------------------- #
#  ORCHESTRATOR                                                                #
# --------------------------------------------------------------------------- #

def render_deck(payload: dict, out_dir: str, logo_path: Optional[str] = None) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    slides = normalize(payload)
    total = len(slides)
    seed = abs(hash(payload.get("headline", "") + str(total))) % 997

    ctx_base = {
        "total": total,
        "seed": seed,
        "kicker": payload.get("kicker", "AI INTELLIGENCE"),
        "handle": payload.get("handle", "@BlocUnited"),
        "source": payload.get("source", ""),
        "date": payload.get("date", ""),
        "cover_image": payload.get("cover_image"),
        "logo_path": logo_path or payload.get("logo_path"),
    }

    paths = []
    for i, slide in enumerate(slides):
        ctx = dict(ctx_base, idx=i)
        renderer = _ROLE_RENDERERS.get(slide["role"], render_body)
        img = renderer(slide, ctx)
        p = os.path.join(out_dir, f"slide_{i + 1:02d}.png")
        img.convert("RGB").save(p, "PNG", optimize=True)
        paths.append(p)
    return paths
