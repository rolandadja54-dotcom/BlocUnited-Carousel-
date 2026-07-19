"""
BlocUnited // plan-driven carousel renderer
===========================================

NOT a fixed template. This renderer consumes a *deck plan* produced by the AI
art director (see art_director.md): each slide names its own `type`, and this
module has one composition block per type. The art director varies the mix each
day, so no two decks look alike. Slides may carry a fal.ai `image_path`; the
renderer overlays crisp brand text on that imagery (text is never baked by the
model, so headlines stay legible).

Slide types: cover · statement · stat · quote · bullets · image_caption ·
             comparison · timeline · explainer · cta

Public entry point:  render_deck(plan, out_dir, logo_path=None, use_fal=False)
"""

from __future__ import annotations

import os
from typing import Optional

from PIL import Image, ImageDraw, ImageOps, ImageFilter

from blocunited_carousel import (
    W, H, MARGIN,
    INK, INK_DEEP, PANEL, BRAND, SIGNAL, WHITE, MUTE, HAIRLINE,
    F_DISPLAY, F_COND, F_BODY, F_BODY_SL, F_MONO, F_MONO_B,
    font, _lerp, vgradient, valpha, add_grain, text_len, wrap, fit_block,
    draw_emph_lines, draw_tracked, tracked_len, place_logo, paint_base,
)

CONTENT_X = MARGIN
CONTENT_W = W - 2 * MARGIN

BLACK = (0, 0, 0)               # text slides use a true-black canvas (brand blue = only accent)


def black_base() -> Image.Image:
    """Pure-black canvas for all text slides. Imagery only appears where a slide
    actually places a fal.ai image (cover / image_caption)."""
    return Image.new("RGB", (W, H), BLACK)


# --------------------------------------------------------------------------- #
#  IMAGE HANDLING  (fal.ai path if present, else a branded placeholder)        #
# --------------------------------------------------------------------------- #

def _local_grain(img: Image.Image, amount: int = 6, seed: int = 0) -> Image.Image:
    import random
    w, h = img.size
    rnd = random.Random(seed)
    noise = Image.new("L", (w // 2, h // 2))
    noise.putdata([128 + rnd.randint(-amount, amount) for _ in range(noise.width * noise.height)])
    noise = noise.resize((w, h)).filter(ImageFilter.GaussianBlur(0.4))
    overlay = Image.merge("RGB", (noise, noise, noise))
    return Image.blend(img, overlay, 0.05)


def placeholder_image(prompt: str, size, seed: int = 0) -> Image.Image:
    """A branded stand-in for a fal.ai image so the pipeline renders today.
    Deep-navy gradient + a soft blue glow + a small honest 'placeholder' tag."""
    import random
    w, h = size
    rnd = random.Random(seed or (len(prompt) + 7))
    base = vgradient((w, h), _lerp(INK, BRAND, 0.28), INK_DEEP).convert("RGBA")

    # soft radial glow, position varies by seed so placeholders aren't identical
    gx = int(w * (0.30 + 0.4 * rnd.random()))
    gy = int(h * (0.25 + 0.3 * rnd.random()))
    R = int(max(w, h) * 0.55)
    glow = Image.new("L", (w, h), 0)
    ImageDraw.Draw(glow).ellipse([gx - R, gy - R, gx + R, gy + R], fill=150)
    glow = glow.filter(ImageFilter.GaussianBlur(R * 0.35))
    tint = Image.new("RGBA", (w, h), (*SIGNAL, 255))
    base = Image.composite(tint, base, glow)

    d = ImageDraw.Draw(base)
    # faint diagonal "scan" lines for a tech texture
    for i in range(-h, w, 46):
        d.line([(i, 0), (i + h, h)], fill=(*WHITE, 8), width=1)
    base = _local_grain(base.convert("RGB"), seed=seed).convert("RGBA")

    # honest tag, CENTERED so it never fights slide furniture (swipe/logo/headline).
    # Real fal.ai art carries no tag; this only marks dev-mode stand-ins.
    d = ImageDraw.Draw(base)
    tf = font(F_MONO, max(16, w // 58))
    tag = "fal.ai image · placeholder"
    tw = text_len(tf, tag)
    cy = h // 2
    d.text(((w - tw) / 2, cy - 16), tag, font=tf, fill=(*WHITE, 130))
    if prompt:
        pf = font(F_MONO, max(14, w // 74))
        snip = "“" + prompt[:52] + ("…" if len(prompt) > 52 else "") + "”"
        pw = text_len(pf, snip)
        d.text(((w - pw) / 2, cy + 18), snip, font=pf, fill=(*WHITE, 85))
    return base.convert("RGB")


def load_slide_image(slide: dict, size, seed: int) -> Image.Image:
    """Return a PIL image for this slide: real fal.ai file if present, else placeholder.
    Fitting to the target box is the caller's job."""
    path = slide.get("image_path")
    if path and os.path.exists(path):
        return Image.open(path).convert("RGB")
    return placeholder_image(slide.get("image_prompt", ""), size, seed)


# --------------------------------------------------------------------------- #
#  SCRIMS + SHARED FURNITURE                                                   #
# --------------------------------------------------------------------------- #

def _vscrim(size, start_frac: float, max_a: int) -> Image.Image:
    """Vertical alpha: transparent until start_frac, then ramps to max_a at bottom."""
    w, h = size
    strip = Image.new("L", (1, h))
    px = strip.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = 0 if t < start_frac else int(max_a * ((t - start_frac) / max(1e-6, 1 - start_frac)))
    return strip.resize((w, h))


def bottom_scrim(img, start=0.42, max_a=255):
    grad = Image.new("RGB", img.size, BLACK)   # fade image into true black (matches text slides)
    return Image.composite(grad, img, _vscrim(img.size, start, max_a))


def top_scrim(img, max_a=150):
    grad = Image.new("RGB", img.size, BLACK)
    m = valpha(img.size, max_a, 0)          # dark at top, clear below
    return Image.composite(grad, img, m)


def draw_kicker(draw, label, y=MARGIN):
    draw.rounded_rectangle([CONTENT_X, y + 6, CONTENT_X + 34, y + 14], radius=3, fill=SIGNAL)
    f = font(F_COND, 30)
    draw_tracked(draw, (CONTENT_X + 48, y - 4), (label or "").upper(), f, MUTE, tracking=3)


def draw_index(draw, idx, total):
    f = font(F_MONO_B, 28)
    s, tot = f"{idx + 1:02d}", f"/{total:02d}"
    totw = text_len(font(F_MONO, 28), tot)
    x = W - MARGIN - totw - text_len(f, s)
    draw.text((x, MARGIN - 6), s, font=f, fill=WHITE)
    draw.text((x + text_len(f, s), MARGIN - 6), tot, font=font(F_MONO, 28), fill=MUTE)


def furniture(img, ctx, idx, extra_kicker=None):
    """Kicker (top-left) + index (top-right) + logo (bottom). Consistent brand frame."""
    draw = ImageDraw.Draw(img)
    draw_kicker(draw, extra_kicker or ctx.get("kicker", "AI INTELLIGENCE"))
    draw_index(draw, idx, ctx["total"])
    place_logo(img, draw, ctx.get("logo_path"))
    return draw


def swipe_hint(draw):
    f = font(F_MONO_B, 24)
    s = "SWIPE"
    x = CONTENT_X
    y = H - 168
    draw.text((x, y), s, font=f, fill=MUTE)
    ax = x + text_len(f, s) + 16
    ay = y + 13
    draw.line([(ax, ay), (ax + 24, ay)], fill=SIGNAL, width=4)
    draw.line([(ax + 15, ay - 7), (ax + 24, ay)], fill=SIGNAL, width=4)
    draw.line([(ax + 15, ay + 7), (ax + 24, ay)], fill=SIGNAL, width=4)


def emphasis_of(slide):
    return set(w.lower() for w in slide.get("emphasis", []))


# --------------------------------------------------------------------------- #
#  SLIDE BLOCKS  (one per type)                                                #
# --------------------------------------------------------------------------- #

def render_cover(slide, ctx, idx):
    """Fully-AI image on TOP (~66%), BlocUnited headline rendered UNDERNEATH on
    pure black. Text is drawn by Python, so the headline is always legible."""
    seed = ctx["seed"] + idx
    img = black_base()

    # --- AI image zone (top ~60%) ---
    img_h = int(H * 0.60)
    src = load_slide_image(slide, (W, img_h), seed)
    photo = ImageOps.fit(src, (W, img_h), centering=(0.5, 0.4)).convert("RGB")
    img.paste(photo, (0, 0))
    # soft fade from the photo into the black headline zone (no hard seam)
    fade_h = 220
    fade = Image.new("RGB", (W, fade_h), BLACK)
    fmask = valpha((W, fade_h), 0, 255)
    img.paste(Image.composite(fade, img.crop((0, img_h - fade_h, W, img_h)), fmask),
              (0, img_h - fade_h))
    img = top_scrim(img, 150)                      # keep kicker/index legible on the photo

    draw = furniture(img, ctx, idx)

    # --- headline zone (black, underneath), clear of swipe + logo ---
    headline = (slide.get("headline") or slide.get("body") or "").strip().upper()
    zone_top = img_h + 30
    zone_h = (H - 200) - zone_top
    f, lines, lh, total_h = fit_block(headline, F_DISPLAY, CONTENT_W, zone_h, 88, 48,
                                      line_gap=1.06, max_lines=4)
    y = zone_top + (zone_h - total_h) // 2
    # brand tick above the headline
    draw.rounded_rectangle([CONTENT_X, y - 30, CONTENT_X + 56, y - 20], radius=4, fill=SIGNAL)
    draw_emph_lines(draw, lines, f, CONTENT_X, y, lh, WHITE, SIGNAL,
                    emphasis_of(slide), align="left", box_w=CONTENT_W)
    swipe_hint(draw)
    return img


def render_statement(slide, ctx, idx):
    img = black_base()
    draw = furniture(img, ctx, idx)
    body = (slide.get("body") or slide.get("text") or "").strip()
    f, lines, lh, total_h = fit_block(body, F_DISPLAY, CONTENT_W, 640, 100, 54,
                                      line_gap=1.12, max_lines=7)
    y = (H - total_h) // 2 - 20
    draw.rounded_rectangle([CONTENT_X, y - 34, CONTENT_X + 64, y - 24], radius=4, fill=SIGNAL)
    draw_emph_lines(draw, lines, f, CONTENT_X, y, lh, WHITE, SIGNAL,
                    emphasis_of(slide), box_w=CONTENT_W)
    swipe_hint(draw)
    return img


def render_stat(slide, ctx, idx):
    img = black_base()
    draw = furniture(img, ctx, idx)
    stat = slide.get("stat", {})
    value = str(stat.get("value", slide.get("value", "")))
    label = stat.get("label", slide.get("body", ""))

    # oversized numeral, auto-fit to width
    vf, vlines, vlh, _ = fit_block(value, F_COND, CONTENT_W, 420, 340, 120,
                                   line_gap=1.0, max_lines=1)
    y = 360
    draw.text((CONTENT_X - 4, y), value, font=vf, fill=SIGNAL)
    vb = vf.getbbox(value)
    y += (vb[3] - vb[1]) + 40
    draw.line([(CONTENT_X, y), (CONTENT_X + 90, y)], fill=SIGNAL, width=6)
    y += 34
    lf = font(F_BODY, 50)
    for ln in wrap(label, lf, CONTENT_W)[:4]:
        draw.text((CONTENT_X, y), ln, font=lf, fill=WHITE)
        y += 62
    swipe_hint(draw)
    return img


def render_quote(slide, ctx, idx):
    img = black_base()
    draw = furniture(img, ctx, idx)
    q = slide.get("quote", {})
    text = q.get("text", slide.get("body", "")).strip()
    author = q.get("author", "")

    qf = font(F_COND, 200)
    draw.text((CONTENT_X - 10, 150), "“", font=qf, fill=(*BRAND, 255))
    f, lines, lh, total_h = fit_block(text, F_DISPLAY, CONTENT_W, 560, 82, 46,
                                      line_gap=1.14, max_lines=8)
    y = (H - total_h) // 2 - 10
    y = draw_emph_lines(draw, lines, f, CONTENT_X, y, lh, WHITE, SIGNAL,
                        emphasis_of(slide), box_w=CONTENT_W)
    if author:
        y += 26
        af = font(F_MONO, 30)
        draw.text((CONTENT_X, y), author, font=af, fill=MUTE)
    swipe_hint(draw)
    return img


def render_bullets(slide, ctx, idx):
    img = black_base()
    draw = furniture(img, ctx, idx)
    y = 250
    title = (slide.get("title") or "").strip()
    if title:
        tf, tlines, tlh, th = fit_block(title, F_DISPLAY, CONTENT_W, 300, 76, 46,
                                        line_gap=1.05, max_lines=3)
        y = draw_emph_lines(draw, tlines, tf, CONTENT_X, y, tlh, WHITE, SIGNAL,
                            emphasis_of(slide), box_w=CONTENT_W)
        y += 44

    items = slide.get("items", [])
    bf = font(F_BODY_SL, 46)
    for it in items[:4]:
        body = it if isinstance(it, str) else it.get("body", "")
        draw.rounded_rectangle([CONTENT_X, y + 8, CONTENT_X + 18, y + 46], radius=5, fill=SIGNAL)
        tx = CONTENT_X + 40
        for ln in wrap(body, bf, CONTENT_W - 40)[:3]:
            draw.text((tx, y), ln, font=bf, fill=_lerp(WHITE, MUTE, 0.10))
            y += 58
        y += 30
    swipe_hint(draw)
    return img


def render_image_caption(slide, ctx, idx):
    seed = ctx["seed"] + idx
    role = slide.get("image_role", "inset")

    if role in ("full", "background"):
        src = load_slide_image(slide, (W, H), seed)
        img = ImageOps.fit(src, (W, H), centering=(0.5, 0.4)).convert("RGB")
        if role == "background":
            img = Image.blend(img, Image.new("RGB", (W, H), INK_DEEP), 0.60)
        img = top_scrim(img, 150)
        img = bottom_scrim(img, start=0.45, max_a=250)
        draw = furniture(img, ctx, idx)
        body = (slide.get("body") or "").strip()
        f, lines, lh, total_h = fit_block(body, F_DISPLAY, CONTENT_W, 380, 72, 42,
                                          line_gap=1.12, max_lines=5)
        y = H - 210 - total_h
        draw_emph_lines(draw, lines, f, CONTENT_X, y, lh, WHITE, SIGNAL,
                        emphasis_of(slide), box_w=CONTENT_W)
        swipe_hint(draw)
        return img

    # inset: framed image card near top, caption below
    img = black_base()
    card_top, card_h = 210, 700
    src = load_slide_image(slide, (CONTENT_W, card_h), seed)
    card = ImageOps.fit(src, (CONTENT_W, card_h), centering=(0.5, 0.4)).convert("RGB")
    mask = Image.new("L", (CONTENT_W, card_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, CONTENT_W, card_h], radius=28, fill=255)
    img.paste(card, (CONTENT_X, card_top), mask)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([CONTENT_X, card_top, CONTENT_X + CONTENT_W, card_top + card_h],
                           radius=28, outline=HAIRLINE, width=2)
    furniture(img, ctx, idx)
    draw = ImageDraw.Draw(img)
    body = (slide.get("body") or "").strip()
    y = card_top + card_h + 46
    bf = font(F_BODY_SL, 46)
    for ln in wrap(body, bf, CONTENT_W)[:3]:
        draw.text((CONTENT_X, y), ln, font=bf, fill=WHITE)
        y += 60
    swipe_hint(draw)
    return img


def render_comparison(slide, ctx, idx):
    img = black_base()
    draw = furniture(img, ctx, idx)
    title = (slide.get("title") or "").strip()
    y0 = 240
    if title:
        tf, tlines, tlh, th = fit_block(title, F_DISPLAY, CONTENT_W, 200, 66, 40,
                                        line_gap=1.05, max_lines=2)
        draw_emph_lines(draw, tlines, tf, CONTENT_X, y0, tlh, WHITE, SIGNAL,
                        emphasis_of(slide), box_w=CONTENT_W)
        y0 += th + 40

    items = slide.get("items", [])[:2]
    if len(items) < 2:
        items = (items + [{"label": "", "body": ""}, {"label": "", "body": ""}])[:2]
    panel_h = 360
    gap = 44
    for i, it in enumerate(items):
        py = y0 + i * (panel_h + gap)
        accent = SIGNAL if i == 0 else _lerp(BRAND, WHITE, 0.15)
        draw.rounded_rectangle([CONTENT_X, py, CONTENT_X + CONTENT_W, py + panel_h],
                               radius=22, fill=PANEL)
        draw.rounded_rectangle([CONTENT_X, py, CONTENT_X + 10, py + panel_h],
                               radius=5, fill=accent)
        lab = (it.get("label") or ("A" if i == 0 else "B")).upper()
        lf = font(F_MONO_B, 30)
        draw.text((CONTENT_X + 40, py + 34), lab, font=lf, fill=accent)
        bf = font(F_BODY_SL, 42)
        ty = py + 92
        for ln in wrap(it.get("body", ""), bf, CONTENT_W - 80)[:4]:
            draw.text((CONTENT_X + 40, ty), ln, font=bf, fill=WHITE)
            ty += 54
    # VS badge between panels
    vy = y0 + panel_h + gap // 2
    r = 34
    cx = W // 2
    draw.ellipse([cx - r, vy - r, cx + r, vy + r], fill=INK, outline=SIGNAL, width=3)
    vf = font(F_COND, 34)
    vb = draw.textbbox((0, 0), "VS", font=vf)
    draw.text((cx - (vb[2] - vb[0]) / 2 - vb[0], vy - (vb[3] - vb[1]) / 2 - vb[1]),
              "VS", font=vf, fill=SIGNAL)
    swipe_hint(draw)
    return img


def render_timeline(slide, ctx, idx):
    img = black_base()
    draw = furniture(img, ctx, idx)
    y = 250
    title = (slide.get("title") or "").strip()
    if title:
        tf, tlines, tlh, th = fit_block(title, F_DISPLAY, CONTENT_W, 240, 70, 44,
                                        line_gap=1.05, max_lines=3)
        y = draw_emph_lines(draw, tlines, tf, CONTENT_X, y, tlh, WHITE, SIGNAL,
                            emphasis_of(slide), box_w=CONTENT_W)
        y += 46

    items = slide.get("items", [])[:4]
    node_x = CONTENT_X + 26
    text_x = CONTENT_X + 92
    bf = font(F_BODY_SL, 44)
    nf = font(F_COND, 34)
    prev_cy = None
    for i, it in enumerate(items):
        label = str(it.get("label", i + 1)) if isinstance(it, dict) else str(i + 1)
        body = it.get("body", "") if isinstance(it, dict) else str(it)
        lines = wrap(body, bf, CONTENT_W - (text_x - CONTENT_X))[:3]
        block_h = max(70, len(lines) * 56)
        cy = y + 30
        if prev_cy is not None:
            draw.line([(node_x, prev_cy + 24), (node_x, cy - 24)], fill=HAIRLINE, width=3)
        draw.ellipse([node_x - 24, cy - 24, node_x + 24, cy + 24], fill=BRAND, outline=SIGNAL, width=3)
        nb = draw.textbbox((0, 0), label, font=nf)
        draw.text((node_x - (nb[2] - nb[0]) / 2 - nb[0], cy - (nb[3] - nb[1]) / 2 - nb[1]),
                  label, font=nf, fill=WHITE)
        ty = y + 4
        for ln in lines:
            draw.text((text_x, ty), ln, font=bf, fill=WHITE)
            ty += 56
        prev_cy = cy
        y += block_h + 40
    swipe_hint(draw)
    return img


def render_explainer(slide, ctx, idx):
    img = black_base()
    draw = furniture(img, ctx, idx, extra_kicker=slide.get("kicker", "WHAT THIS MEANS"))
    y = 300
    title = (slide.get("title") or "").strip()
    if title and title.upper() != "WHAT THIS MEANS":
        tf, tlines, tlh, th = fit_block(title, F_DISPLAY, CONTENT_W, 300, 80, 46,
                                        line_gap=1.05, max_lines=3)
        y = draw_emph_lines(draw, tlines, tf, CONTENT_X, y, tlh, WHITE, SIGNAL,
                            emphasis_of(slide), box_w=CONTENT_W)
        draw.line([(CONTENT_X, y + 20), (CONTENT_X + 80, y + 20)], fill=SIGNAL, width=5)
        y += 60
    body = (slide.get("body") or "").strip()
    bf = font(F_BODY_SL, 50)
    for ln in wrap(body, bf, CONTENT_W)[:8]:
        draw.text((CONTENT_X, y), ln, font=bf, fill=_lerp(WHITE, MUTE, 0.06))
        y += 66
    swipe_hint(draw)
    return img


def render_cta(slide, ctx, idx):
    img = black_base()
    draw = furniture(img, ctx, idx, extra_kicker="YOUR MOVE")

    prompt = (slide.get("body") or slide.get("share_prompt")
              or "Know someone who needs this? Send it their way.").strip()
    f, lines, lh, total_h = fit_block(prompt, F_DISPLAY, CONTENT_W, 460, 86, 46,
                                      line_gap=1.12, max_lines=6)
    y = 300
    y = draw_emph_lines(draw, lines, f, CONTENT_X, y, lh, WHITE, SIGNAL,
                        emphasis_of(slide), box_w=CONTENT_W)
    y += 46
    handle = ctx.get("handle", "@BlocUnited")
    ff = font(F_COND, 50)
    ftxt = f"FOLLOW  {handle}"
    fb = ff.getbbox(ftxt)
    pill_w, pill_h = (fb[2] - fb[0]) + 88, 86
    draw.rounded_rectangle([CONTENT_X, y, CONTENT_X + pill_w, y + pill_h],
                           radius=pill_h // 2, fill=SIGNAL)
    draw.text((CONTENT_X + 44, y + (pill_h - (fb[3] - fb[1])) / 2 - fb[1]),
              ftxt, font=ff, fill=INK)
    return img


BLOCKS = {
    "cover": render_cover,
    "statement": render_statement,
    "stat": render_stat,
    "quote": render_quote,
    "bullets": render_bullets,
    "image_caption": render_image_caption,
    "comparison": render_comparison,
    "timeline": render_timeline,
    "explainer": render_explainer,
    "cta": render_cta,
}


# --------------------------------------------------------------------------- #
#  ORCHESTRATOR                                                                #
# --------------------------------------------------------------------------- #

def _normalize(plan: dict) -> list[dict]:
    slides = [dict(s) for s in plan.get("slides", [])]
    if not slides:
        raise ValueError("Deck plan has no slides.")
    # guarantee cover first / cta last so the deck always frames correctly
    if slides[0].get("type") != "cover":
        slides[0]["type"] = "cover"
        slides[0].setdefault("headline", plan.get("headline", ""))
    if slides[-1].get("type") != "cta":
        slides.append({"type": "cta", "body": plan.get("share_prompt", "")})
    for s in slides:
        s.setdefault("type", "statement")
    return slides


def render_deck(plan: dict, out_dir: str, logo_path: Optional[str] = None,
                use_fal: bool = False) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    slides = _normalize(plan)
    total = len(slides)
    seed = abs(hash(plan.get("headline", "") + str(total))) % 997

    ctx = {
        "total": total,
        "seed": seed,
        "kicker": plan.get("kicker", "AI INTELLIGENCE"),
        "handle": plan.get("handle", "@BlocUnited"),
        "logo_path": logo_path or plan.get("logo_path"),
        "use_fal": use_fal,
    }

    # resolve fal.ai imagery up front (falls back to placeholder on any failure)
    if use_fal:
        try:
            import fal_image
        except Exception:
            fal_image = None
        for i, s in enumerate(slides):
            if s.get("image_prompt") and not s.get("image_path") and fal_image:
                try:
                    p = os.path.join(out_dir, f"_img_{i + 1:02d}.png")
                    fal_image.generate(s["image_prompt"], p)
                    s["image_path"] = p
                except Exception as e:
                    print(f"  ! fal.ai failed for slide {i + 1} ({e}); using placeholder")

    paths = []
    for i, slide in enumerate(slides):
        block = BLOCKS.get(slide.get("type"), render_statement)
        img = block(slide, ctx, i).convert("RGB")
        p = os.path.join(out_dir, f"slide_{i + 1:02d}.png")
        img.save(p, "PNG", optimize=True)
        paths.append(p)
    return paths
