#!/usr/bin/env python3
"""
Meridian Atlas Co. — Social Asset Generator v2 (mockup-first)
==============================================================
PRINCIPIO: i mockup dell'utente sono asset FINITI. Lo script non li compone,
non li decora, non ci scrive sopra (salvo flag esplicito): li riadatta solo
ai formati piattaforma. Gli asset derivati dall'artwork (detail, card
tipografica, reel) sono contenuti AGGIUNTIVI per i pilastri Process/City Story.

Input per citta'  (assets/social/ma-NN-citta/src/):
  artwork.(png|jpg)        mappa master orizzontale 3:2
  mockups/*.jpg|png        TUTTI i mockup finiti, qualsiasi numero/nome
  meta.json                dati + opzioni (vedi DEFAULTS)
  reel.mp4                 opzionale (Higgsfield); se assente -> Ken Burns

Output (cartella citta'):
  per ogni mockup <nome>:   <nome>-pin.jpg    1000x1500  passthrough
                            <nome>-feed.jpg   1080x1350  crop 4:5
                            <nome>-story.jpg  1080x1920  bande avorio o full-bleed
  dall'artwork:             feed-artwork.jpg  1080x1350
                            feed-detail.jpg   1080x1350
                            feed-card.jpg     1080x1350  (tipografica)
                            story-artwork.jpg 1080x1920
                            pin-typo.jpg      1000x1500  (variante anti-duplicato)
                            reel.mp4          1080x1920

Opzioni in meta.json (tutte facoltative):
  "feed_crop":   "top" | "center" | "bottom"   default "top"
                 quale parte del mockup CONSERVARE nel taglio 4:5
                 ("top" protegge il testo brand nei 220px superiori)
  "story_mode":  "bands" | "fill"              default "bands"
  "overlay_pins": true | false                 default false
                 se true scrive citta'+serie nei 220px top dei pin
                 (solo se i tuoi mockup NON hanno gia' il testo)

Uso:  python tools/generate_social_assets.py assets/social/ma-01-milano
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ----------------------------------------------------------------- brand ----
IVORY = (242, 237, 226)        # F2EDE2
BLACK = (26, 26, 26)           # 1A1A1A
GRAY = (138, 131, 117)
HAIR = (26, 26, 26)
JPEG_Q = 88

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "social" / "_fonts"
F_PLAYFAIR = FONT_DIR / "PlayfairDisplay-Bold.ttf"
F_INTER_R = FONT_DIR / "Inter-Regular.ttf"
F_INTER_M = FONT_DIR / "Inter-Medium.ttf"
F_INTER_SB = FONT_DIR / "Inter-SemiBold.ttf"

DEFAULTS = {"feed_crop": "top", "story_mode": "bands", "overlay_pins": False}


# ----------------------------------------------------------------- utils ----
def font(path, size):
    return ImageFont.truetype(str(path), size)


def tracked_width(draw, text, fnt, tracking):
    if not text:
        return 0
    return sum(draw.textlength(c, font=fnt) for c in text) + tracking * (len(text) - 1)


def draw_tracked(draw, cx, y, text, fnt, tracking, fill):
    total = tracked_width(draw, text, fnt, tracking)
    x = cx - total / 2
    asc, desc = fnt.getmetrics()
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking
    return asc + desc


def fit_font(path, text, max_w, start, minimum=40, tracking=0):
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    size = start
    while size > minimum:
        f = font(path, size)
        if tracked_width(probe, text, f, tracking) <= max_w:
            return f
        size -= 4
    return font(path, minimum)


def paste_keyline(canvas, img, x, y, line=2):
    canvas.paste(img, (x, y))
    ImageDraw.Draw(canvas).rectangle(
        [x, y, x + img.width - 1, y + img.height - 1], outline=HAIR, width=line
    )


def fit_width(img, w):
    return img.resize((w, round(img.height * w / img.width)), Image.LANCZOS)


def crop_anchored(img, tw, th, anchor="center"):
    """Ritaglio al rapporto tw:th senza deformare. anchor = top|center|bottom
    decide quale parte CONSERVARE quando si taglia in altezza."""
    target = tw / th
    w, h = img.size
    if w / h > target:                       # troppo largo: taglio i lati, centrato
        cw = h * target
        left = (w - cw) / 2
        box = (left, 0, left + cw, h)
    else:                                    # troppo alto: taglio in verticale
        ch = w / target
        excess = h - ch
        top = {"top": 0, "bottom": excess}.get(anchor, excess / 2)
        box = (0, top, w, top + ch)
    out = img.crop(tuple(round(v) for v in box))
    return out.resize((tw, th), Image.LANCZOS)


def crop_zoom(img, tw, th, cx=0.5, cy=0.5, zoom=1.0):
    target = tw / th
    w, h = img.size
    if w / h > target:
        ch = h / zoom
        cw = ch * target
    else:
        cw = w / zoom
        ch = cw / target
    left = min(max(cx * w - cw / 2, 0), w - cw)
    top = min(max(cy * h - ch / 2, 0), h - ch)
    out = img.crop((round(left), round(top), round(left + cw), round(top + ch)))
    return out.resize((tw, th), Image.LANCZOS)


def save_jpg(img, path):
    img.convert("RGB").save(path, "JPEG", quality=JPEG_Q, optimize=True)
    print(f"  ok  {path.name}  {img.size[0]}x{img.size[1]}")


def diamond(d, cx, cy, r=7):
    d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=BLACK)


# --------------------------------------------------- mockup passthrough -----
def mockup_pin(name, img, meta, opts, out):
    """Pin 1000x1500: contenuto intatto. Resize/crop solo se il file non e' gia' 2:3."""
    pin = img if img.size == (1000, 1500) else crop_anchored(img, 1000, 1500, "center")
    if opts["overlay_pins"]:
        pin = pin.copy()
        d = ImageDraw.Draw(pin)
        f_city = fit_font(F_PLAYFAIR, meta["city"], 780, 64, 40)
        y = 52
        y += draw_tracked(d, 500, y, meta["city"], f_city, 4, BLACK) + 14
        draw_tracked(d, 500, y, f"CITY ATLAS — NO. {meta['nn']}", font(F_INTER_M, 20), 7, BLACK)
    save_jpg(pin, out / f"{name}-pin.jpg")


def mockup_feed(name, img, opts, out):
    """Feed 4:5 1080x1350: solo ritaglio, ancorato per non perdere il testo in alto."""
    save_jpg(crop_anchored(img, 1080, 1350, opts["feed_crop"]), out / f"{name}-feed.jpg")


def mockup_story(name, img, opts, out):
    """Story 9:16. 'bands': mockup integro tra bande avorio (brand sopra, CTA sotto).
    'fill': full-bleed con ritaglio laterale centrato."""
    if opts["story_mode"] == "fill":
        save_jpg(crop_anchored(img, 1080, 1920, "center"), out / f"{name}-story.jpg")
        return
    top_b, bot_b = 170, 130
    c = Image.new("RGB", (1080, 1920), IVORY)
    body = crop_anchored(img, 1080, 1920 - top_b - bot_b, "center")
    c.paste(body, (0, top_b))
    d = ImageDraw.Draw(c)
    d.line([(0, top_b), (1080, top_b)], fill=HAIR, width=1)
    d.line([(0, 1920 - bot_b), (1080, 1920 - bot_b)], fill=HAIR, width=1)
    f_top = font(F_INTER_M, 24)
    asc, desc = f_top.getmetrics()
    draw_tracked(d, 540, (top_b - asc - desc) // 2, "MERIDIAN ATLAS CO.", f_top, 8, BLACK)
    cta = "AVAILABLE AS A PREMIUM PRINT — LINK IN BIO"
    f_bot = fit_font(F_INTER_SB, cta, 980, 24, 14, tracking=6)
    asc, desc = f_bot.getmetrics()
    draw_tracked(d, 540, 1920 - bot_b + (bot_b - asc - desc) // 2, cta, f_bot, 6, BLACK)
    save_jpg(c, out / f"{name}-story.jpg")


# ------------------------------------------------- artwork-derived extra ----
def feed_artwork(artwork, meta, out):
    c = Image.new("RGB", (1080, 1350), IVORY)
    d = ImageDraw.Draw(c)
    art = fit_width(artwork, 940)
    line1 = f"CITY ATLAS — {meta['city']} — NO. {meta['nn']}"
    f1 = fit_font(F_INTER_SB, line1, 940, 30, 20, tracking=8)
    f2 = font(F_INTER_M, 20)
    block = art.height + 64 + 34 + 24 + 24
    top = max((1350 - block) // 2 - 14, 90)
    paste_keyline(c, art, (1080 - art.width) // 2, top)
    y = top + art.height + 64
    y += draw_tracked(d, 540, y, line1, f1, 8, BLACK) + 18
    draw_tracked(d, 540, y, "MERIDIAN ATLAS CO.", f2, 7, GRAY)
    save_jpg(c, out / "feed-artwork.jpg")


def feed_detail(artwork, meta, out):
    band = 110
    img_h = 1350 - band
    det = crop_zoom(artwork, 1080, img_h, cx=0.50, cy=0.46, zoom=2.1)
    c = Image.new("RGB", (1080, 1350), IVORY)
    c.paste(det, (0, 0))
    d = ImageDraw.Draw(c)
    d.line([(0, img_h), (1080, img_h)], fill=HAIR, width=1)
    txt = f"THE DETAIL — {meta['city']} — NO. {meta['nn']}"
    f1 = fit_font(F_INTER_SB, txt, 980, 24, 16, tracking=7)
    asc, desc = f1.getmetrics()
    draw_tracked(d, 540, img_h + (band - asc - desc) // 2, txt, f1, 7, BLACK)
    save_jpg(c, out / "feed-detail.jpg")


def feed_card(meta, out):
    c = Image.new("RGB", (1080, 1350), IVORY)
    d = ImageDraw.Draw(c)
    f_over = font(F_INTER_M, 24)
    f_city = fit_font(F_PLAYFAIR, meta["city"], 920, 170, 80)
    f_country = font(F_INTER_M, 30)
    f_coords = font(F_INTER_R, 30)
    h_city = sum(f_city.getmetrics())
    block = 24 + 64 + h_city + 30 + 30 + 56 + 14 + 56 + 30
    y = (1350 - block) // 2 - 30
    y += draw_tracked(d, 540, y, f"CITY ATLAS — NO. {meta['nn']}", f_over, 9, GRAY) + 64
    y += draw_tracked(d, 540, y, meta["city"], f_city, 6, BLACK) + 30
    y += draw_tracked(d, 540, y, meta["country"], f_country, 12, BLACK) + 56
    diamond(d, 540, y + 7)
    y += 14 + 56
    y += draw_tracked(d, 540, y, meta["coords"], f_coords, 2, GRAY)
    draw_tracked(d, 540, 1350 - 150, "MERIDIAN ATLAS CO.", font(F_INTER_M, 20), 7, GRAY)
    save_jpg(c, out / "feed-card.jpg")


def story_artwork(artwork, meta, out):
    c = Image.new("RGB", (1080, 1920), IVORY)
    d = ImageDraw.Draw(c)
    f_over = font(F_INTER_M, 26)
    f_city = fit_font(F_PLAYFAIR, meta["city"], 880, 120, 70)
    art = fit_width(artwork, 920)
    h_city = sum(f_city.getmetrics())
    block = 26 + 52 + h_city + 86 + art.height + 104 + 26 + 28 + 22
    y = 250 + (1420 - block) // 2
    y += draw_tracked(d, 540, y, f"CITY ATLAS — NO. {meta['nn']}", f_over, 9, GRAY) + 52
    y += draw_tracked(d, 540, y, meta["city"], f_city, 5, BLACK) + 86
    paste_keyline(c, art, (1080 - art.width) // 2, y)
    y += art.height + 104
    y += draw_tracked(d, 540, y, "AVAILABLE AS A PREMIUM PRINT", font(F_INTER_SB, 26), 8, BLACK) + 28
    draw_tracked(d, 540, y, "LINK IN BIO", font(F_INTER_M, 22), 8, GRAY)
    save_jpg(c, out / "story-artwork.jpg")


def pin_typo(artwork, meta, out):
    """Pin tipografico su avorio: variante visiva DISTINTA dai tuoi pin mockup,
    utile contro la penalita' duplicati nella cadenza multi-board."""
    c = Image.new("RGB", (1000, 1500), IVORY)
    d = ImageDraw.Draw(c)
    f_city = fit_font(F_PLAYFAIR, meta["city"], 840, 110, 64)
    art = fit_width(artwork, 880)
    y = 110
    y += draw_tracked(d, 500, y, f"CITY ATLAS — NO. {meta['nn']}", font(F_INTER_M, 22), 8, GRAY) + 38
    y += draw_tracked(d, 500, y, meta["city"], f_city, 5, BLACK) + 56
    paste_keyline(c, art, (1000 - art.width) // 2, y)
    y += art.height + 66
    draw_tracked(d, 500, y, "EDITORIAL WALL ART — PREMIUM PRINT", font(F_INTER_M, 22), 7, GRAY)
    draw_tracked(d, 500, 1500 - 120, "MERIDIANATLAS.CO", font(F_INTER_SB, 20), 6, BLACK)
    save_jpg(c, out / "pin-typo.jpg")


def reel(artwork_path, src, out):
    custom = src / "reel.mp4"
    target = out / "reel.mp4"
    if custom.exists():
        shutil.copy(custom, target)
        print("  ok  reel.mp4  (copiato da src — Higgsfield)")
        return
    vf = (
        "scale=-2:3840:flags=lanczos,"
        "crop=2160:3840:(in_w-2160)/2:0,"
        "zoompan=z='1+0.0007*on':d=1"
        ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(artwork_path),
         "-t", "6", "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-map_metadata", "-1",
         "-an", str(target)],
        check=True,
    )
    print("  ok  reel.mp4  (Ken Burns 6s 1080x1920)")


# ------------------------------------------------------------------ main ----
def find(src, stem):
    for ext in (".png", ".jpg", ".jpeg"):
        p = src / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def main(city_dir):
    folder = Path(city_dir)
    src = folder / "src"
    if not src.is_dir():
        sys.exit(f"errore: manca {src}")
    meta_p = src / "meta.json"
    if not meta_p.exists():
        sys.exit(f"errore: manca {meta_p}")
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    for k in ("nn", "city", "country", "coords"):
        if k not in meta:
            sys.exit(f"errore: meta.json senza campo '{k}'")
    opts = {**DEFAULTS, **{k: meta[k] for k in DEFAULTS if k in meta}}

    art_p = find(src, "artwork")
    if not art_p:
        sys.exit("errore: manca src/artwork.(png|jpg)")
    artwork = Image.open(art_p).convert("RGB")
    print(f"[{folder.name}]  {meta['city']} No. {meta['nn']}  artwork {artwork.size}  opts {opts}")

    # 1) Mockup dell'utente: passthrough + riadattamento formato
    mock_dir = src / "mockups"
    mocks = sorted(
        p for p in mock_dir.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    ) if mock_dir.is_dir() else []
    legacy = find(src, "mockup")             # retrocompatibilita' v1
    if legacy and not mocks:
        mocks = [legacy]
    if not mocks:
        print("  !!  nessun mockup in src/mockups/: genero solo asset artwork-based")
    for p in mocks:
        name = p.stem.lower().replace(" ", "-")
        img = Image.open(p).convert("RGB")
        mockup_pin(name, img, meta, opts, folder)
        mockup_feed(name, img, opts, folder)
        mockup_story(name, img, opts, folder)

    # 2) Asset extra derivati dall'artwork (pilastri Process / City Story)
    feed_artwork(artwork, meta, folder)
    feed_detail(artwork, meta, folder)
    feed_card(meta, folder)
    story_artwork(artwork, meta, folder)
    pin_typo(artwork, meta, folder)
    reel(art_p, src, folder)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("uso: python tools/generate_social_assets.py assets/social/ma-NN-citta")
    main(sys.argv[1])
