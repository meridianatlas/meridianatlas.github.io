#!/usr/bin/env python3
"""
Meridian Atlas Co. — Social Asset Generator
============================================
Genera automaticamente tutti gli asset social di una citta' a partire da:
  src/artwork.(png|jpg)  -> mappa master (orizzontale 3:2)
  src/mockup.(png|jpg)   -> mockup Gemini 1000x1500 (2:3), opzionale
  src/meta.json          -> {"nn","city","country","coords"}
  src/reel.mp4           -> opzionale (Higgsfield); se assente, Ken Burns ffmpeg

Output (nella cartella citta', accanto a src/):
  feed-a.jpg  1080x1350  Artwork hero (pilastro Artwork)
  feed-b.jpg  1080x1350  Mockup crop (pilastro In Context)      [richiede mockup]
  feed-c.jpg  1080x1350  Detail crop (pilastro Process)
  feed-d.jpg  1080x1350  Typographic card (pilastro City Story)
  story-1.jpg 1080x1920  Mockup story                            [richiede mockup]
  story-2.jpg 1080x1920  Artwork story + CTA
  pin-hero.jpg   1000x1500  Pin artwork con titolo
  pin-mockup.jpg 1000x1500  Pin mockup con overlay nei 220px top [richiede mockup]
  reel.mp4    1080x1920  Ken Burns sull'artwork (o copia src/reel.mp4)

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
GRAY = (138, 131, 117)         # warm gray scurito per testo secondario su avorio
HAIR = (26, 26, 26)

JPEG_Q = 88
FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "social" / "_fonts"

F_PLAYFAIR = FONT_DIR / "PlayfairDisplay-Bold.ttf"
F_INTER_R = FONT_DIR / "Inter-Regular.ttf"
F_INTER_M = FONT_DIR / "Inter-Medium.ttf"
F_INTER_SB = FONT_DIR / "Inter-SemiBold.ttf"


# ----------------------------------------------------------------- utils ----
def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def tracked_width(draw, text, fnt, tracking):
    if not text:
        return 0
    return sum(draw.textlength(c, font=fnt) for c in text) + tracking * (len(text) - 1)


def draw_tracked(draw, cx, y, text, fnt, tracking, fill):
    """Testo con letterspacing manuale, centrato su cx. Ritorna l'altezza riga."""
    total = tracked_width(draw, text, fnt, tracking)
    x = cx - total / 2
    asc, desc = fnt.getmetrics()
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking
    return asc + desc


def fit_font(path: Path, text, max_w, start, minimum=40, tracking=0):
    """Riduce la dimensione del font finche' il testo (con tracking) entra in max_w."""
    probe = Image.new("RGB", (10, 10))
    d = ImageDraw.Draw(probe)
    size = start
    while size > minimum:
        f = font(path, size)
        if tracked_width(d, text, f, tracking) <= max_w:
            return f
        size -= 4
    return font(path, minimum)


def paste_keyline(canvas, img, x, y, line=2):
    canvas.paste(img, (x, y))
    d = ImageDraw.Draw(canvas)
    d.rectangle([x, y, x + img.width - 1, y + img.height - 1], outline=HAIR, width=line)


def fit_width(img, w):
    h = round(img.height * w / img.width)
    return img.resize((w, h), Image.LANCZOS)


def crop_ratio(img, ratio_w, ratio_h, cx=0.5, cy=0.5, zoom=1.0):
    """Ritaglia la massima area con rapporto dato, centrata su (cx,cy), con zoom>1 = piu' stretto."""
    target = ratio_w / ratio_h
    w, h = img.size
    if w / h > target:
        ch = h / zoom
        cw = ch * target
    else:
        cw = w / zoom
        ch = cw / target
    left = min(max(cx * w - cw / 2, 0), w - cw)
    top = min(max(cy * h - ch / 2, 0), h - ch)
    return img.crop((round(left), round(top), round(left + cw), round(top + ch)))


def save_jpg(img, path):
    img.convert("RGB").save(path, "JPEG", quality=JPEG_Q, optimize=True)
    print(f"  ok  {path.name}  {img.size[0]}x{img.size[1]}")


# ------------------------------------------------------------- templates ----
def feed_a(artwork, meta, out):
    """Artwork hero 1080x1350: mappa su avorio + caption editoriale."""
    c = Image.new("RGB", (1080, 1350), IVORY)
    d = ImageDraw.Draw(c)
    art = fit_width(artwork, 940)
    cap1 = font(F_INTER_SB, 30)
    cap2 = font(F_INTER_M, 20)
    line1 = f"CITY ATLAS — {meta['city']} — NO. {meta['nn']}"
    f1 = fit_font(F_INTER_SB, line1, 940, 30, 20, tracking=8)
    block = art.height + 64 + 34 + 24 + 24
    top = max((1350 - block) // 2 - 14, 90)
    paste_keyline(c, art, (1080 - art.width) // 2, top)
    y = top + art.height + 64
    y += draw_tracked(d, 540, y, line1, f1, 8, BLACK) + 18
    draw_tracked(d, 540, y, "MERIDIAN ATLAS CO.", cap2, 7, GRAY)
    save_jpg(c, out / "feed-a.jpg")


def feed_c(artwork, meta, out):
    """Detail crop 1080x1350: zoom sulla trama urbana + banda didascalia."""
    band = 110
    img_h = 1350 - band
    det = crop_ratio(artwork, 1080, img_h, cx=0.50, cy=0.46, zoom=2.1)
    det = det.resize((1080, img_h), Image.LANCZOS)
    c = Image.new("RGB", (1080, 1350), IVORY)
    c.paste(det, (0, 0))
    d = ImageDraw.Draw(c)
    d.line([(0, img_h), (1080, img_h)], fill=HAIR, width=1)
    f1 = font(F_INTER_SB, 24)
    txt = f"THE DETAIL — {meta['city']} — NO. {meta['nn']}"
    f1 = fit_font(F_INTER_SB, txt, 980, 24, 16, tracking=7)
    asc, desc = f1.getmetrics()
    draw_tracked(d, 540, img_h + (band - asc - desc) // 2, txt, f1, 7, BLACK)
    save_jpg(c, out / "feed-c.jpg")


def diamond(d, cx, cy, r=7):
    d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=BLACK)


def feed_d(meta, out):
    """Typographic city card 1080x1350 (pilastro City Story)."""
    c = Image.new("RGB", (1080, 1350), IVORY)
    d = ImageDraw.Draw(c)
    f_over = font(F_INTER_M, 24)
    f_city = fit_font(F_PLAYFAIR, meta["city"], 920, 170, 80)
    f_country = font(F_INTER_M, 30)
    f_coords = font(F_INTER_R, 30)
    f_brand = font(F_INTER_M, 20)

    h_city = sum(f_city.getmetrics())
    block = 24 + 64 + h_city + 30 + 30 + 56 + 14 + 56 + 30
    y = (1350 - block) // 2 - 30
    y += draw_tracked(d, 540, y, f"CITY ATLAS — NO. {meta['nn']}", f_over, 9, GRAY) + 64
    y += draw_tracked(d, 540, y, meta["city"], f_city, 6, BLACK) + 30
    y += draw_tracked(d, 540, y, meta["country"], f_country, 12, BLACK) + 56
    diamond(d, 540, y + 7)
    y += 14 + 56
    y += draw_tracked(d, 540, y, meta["coords"], f_coords, 2, GRAY)
    draw_tracked(d, 540, 1350 - 150, "MERIDIAN ATLAS CO.", f_brand, 7, GRAY)
    save_jpg(c, out / "feed-d.jpg")


def feed_b(mockup, out):
    """In Context 1080x1350: crop 4:5 del mockup (toglie quota top riservata)."""
    w, h = mockup.size                     # atteso 1000x1500
    target_h = round(w * 1350 / 1080)
    excess = h - target_h
    top = round(excess * 0.8)              # mangia soprattutto lo spazio testo in alto
    crop = mockup.crop((0, top, w, top + target_h))
    crop = crop.resize((1080, 1350), Image.LANCZOS)
    save_jpg(crop, out / "feed-b.jpg")


def story_1(mockup, meta, out):
    """Story mockup 1080x1920: bande avorio + mockup pieno."""
    top_band, bot_band = 170, 130
    c = Image.new("RGB", (1080, 1920), IVORY)
    d = ImageDraw.Draw(c)
    m = mockup.resize((1080, 1920 - top_band - bot_band), Image.LANCZOS)
    c.paste(m, (0, top_band))
    d.line([(0, top_band), (1080, top_band)], fill=HAIR, width=1)
    d.line([(0, 1920 - bot_band), (1080, 1920 - bot_band)], fill=HAIR, width=1)
    f_top = font(F_INTER_M, 24)
    f_bot = font(F_INTER_SB, 24)
    asc, desc = f_top.getmetrics()
    draw_tracked(d, 540, (top_band - asc - desc) // 2, "MERIDIAN ATLAS CO.", f_top, 8, BLACK)
    txt = f"{meta['city']} — NO. {meta['nn']}"
    f_bot = fit_font(F_INTER_SB, txt, 980, 24, 16, tracking=7)
    asc, desc = f_bot.getmetrics()
    draw_tracked(d, 540, 1920 - bot_band + (bot_band - asc - desc) // 2, txt, f_bot, 7, BLACK)
    save_jpg(c, out / "story-1.jpg")


def story_2(artwork, meta, out):
    """Story artwork 1080x1920: tipografia + mappa + CTA (safe zones IG rispettate)."""
    c = Image.new("RGB", (1080, 1920), IVORY)
    d = ImageDraw.Draw(c)
    f_over = font(F_INTER_M, 26)
    f_city = fit_font(F_PLAYFAIR, meta["city"], 880, 120, 70)
    f_cta1 = font(F_INTER_SB, 26)
    f_cta2 = font(F_INTER_M, 22)
    art = fit_width(artwork, 920)
    h_city = sum(f_city.getmetrics())
    block = 26 + 52 + h_city + 86 + art.height + 104 + 26 + 28 + 22
    y = 250 + (1420 - block) // 2          # tra le safe zone IG (250 top / 250 bottom)
    y += draw_tracked(d, 540, y, f"CITY ATLAS — NO. {meta['nn']}", f_over, 9, GRAY) + 52
    y += draw_tracked(d, 540, y, meta["city"], f_city, 5, BLACK) + 86
    paste_keyline(c, art, (1080 - art.width) // 2, y)
    y += art.height + 104
    y += draw_tracked(d, 540, y, "AVAILABLE AS A PREMIUM PRINT", f_cta1, 8, BLACK) + 28
    draw_tracked(d, 540, y, "LINK IN BIO", f_cta2, 8, GRAY)
    save_jpg(c, out / "story-2.jpg")


def pin_hero(artwork, meta, out):
    """Pin hero 1000x1500: titolo + mappa + tagline + dominio."""
    c = Image.new("RGB", (1000, 1500), IVORY)
    d = ImageDraw.Draw(c)
    f_over = font(F_INTER_M, 22)
    f_city = fit_font(F_PLAYFAIR, meta["city"], 840, 110, 64)
    f_tag = font(F_INTER_M, 22)
    f_site = font(F_INTER_SB, 20)
    art = fit_width(artwork, 880)
    y = 110
    y += draw_tracked(d, 500, y, f"CITY ATLAS — NO. {meta['nn']}", f_over, 8, GRAY) + 38
    y += draw_tracked(d, 500, y, meta["city"], f_city, 5, BLACK) + 56
    paste_keyline(c, art, (1000 - art.width) // 2, y)
    y += art.height + 66
    y += draw_tracked(d, 500, y, "EDITORIAL WALL ART — PREMIUM PRINT", f_tag, 7, GRAY) + 0
    draw_tracked(d, 500, 1500 - 120, "MERIDIANATLAS.CO", f_site, 6, BLACK)
    save_jpg(c, out / "pin-hero.jpg")


def pin_mockup(mockup, meta, out):
    """Pin mockup 1000x1500: overlay brand nei 220px superiori riservati."""
    c = mockup.resize((1000, 1500), Image.LANCZOS).convert("RGB")
    d = ImageDraw.Draw(c)
    f_city = fit_font(F_PLAYFAIR, meta["city"], 780, 64, 40)
    f_sub = font(F_INTER_M, 20)
    y = 52
    y += draw_tracked(d, 500, y, meta["city"], f_city, 4, BLACK) + 14
    draw_tracked(d, 500, y, f"CITY ATLAS — NO. {meta['nn']}", f_sub, 7, BLACK)
    save_jpg(c, out / "pin-mockup.jpg")


def reel(artwork_path: Path, src: Path, out: Path):
    """reel.mp4: copia src/reel.mp4 se esiste, altrimenti Ken Burns ffmpeg sull'artwork."""
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
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-loop", "1",
        "-i", str(artwork_path), "-t", "6", "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-map_metadata", "-1", "-an", str(target),
    ]
    subprocess.run(cmd, check=True)
    print("  ok  reel.mp4  (Ken Burns 6s 1080x1920)")


# ------------------------------------------------------------------ main ----
def find(src: Path, stem: str):
    for ext in (".png", ".jpg", ".jpeg"):
        p = src / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def main(city_dir: str):
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

    art_p = find(src, "artwork")
    if not art_p:
        sys.exit("errore: manca src/artwork.(png|jpg)")
    artwork = Image.open(art_p).convert("RGB")

    print(f"[{folder.name}]  {meta['city']} No. {meta['nn']}  artwork {artwork.size}")
    feed_a(artwork, meta, folder)
    feed_c(artwork, meta, folder)
    feed_d(meta, folder)
    story_2(artwork, meta, folder)
    pin_hero(artwork, meta, folder)
    reel(art_p, src, folder)

    mock_p = find(src, "mockup")
    if mock_p:
        mockup = Image.open(mock_p).convert("RGB")
        feed_b(mockup, folder)
        story_1(mockup, meta, folder)
        pin_mockup(mockup, meta, folder)
    else:
        print("  !!  mockup assente: saltati feed-b, story-1, pin-mockup")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("uso: python tools/generate_social_assets.py assets/social/ma-NN-citta")
    main(sys.argv[1])
