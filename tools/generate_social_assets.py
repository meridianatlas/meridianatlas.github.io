#!/usr/bin/env python3
"""
Meridian Atlas Co. - Social Asset Generator v2 (mockup-first)
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
                            pin-detail.jpg    1000x1500  (dettaglio verticale 2:3)
                            pin-card.jpg      1000x1500  (card coordinate 2:3)
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
import html as html_lib
import shutil
import subprocess
import sys
import unicodedata
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
        draw_tracked(d, 500, y, f"CITY ATLAS - NO. {meta['nn']}", font(F_INTER_M, 20), 7, BLACK)
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
    cta = "AVAILABLE AS A PREMIUM PRINT - LINK IN BIO"
    f_bot = fit_font(F_INTER_SB, cta, 980, 24, 14, tracking=6)
    asc, desc = f_bot.getmetrics()
    draw_tracked(d, 540, 1920 - bot_b + (bot_b - asc - desc) // 2, cta, f_bot, 6, BLACK)
    save_jpg(c, out / f"{name}-story.jpg")


# ------------------------------------------------- artwork-derived extra ----
def feed_artwork(artwork, meta, out):
    c = Image.new("RGB", (1080, 1350), IVORY)
    d = ImageDraw.Draw(c)
    art = fit_width(artwork, 940)
    line1 = f"CITY ATLAS - {meta['city']} - NO. {meta['nn']}"
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
    txt = f"THE DETAIL - {meta['city']} - NO. {meta['nn']}"
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
    y += draw_tracked(d, 540, y, f"CITY ATLAS - NO. {meta['nn']}", f_over, 9, GRAY) + 64
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
    y += draw_tracked(d, 540, y, f"CITY ATLAS - NO. {meta['nn']}", f_over, 9, GRAY) + 52
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
    y += draw_tracked(d, 500, y, f"CITY ATLAS - NO. {meta['nn']}", font(F_INTER_M, 22), 8, GRAY) + 38
    y += draw_tracked(d, 500, y, meta["city"], f_city, 5, BLACK) + 56
    paste_keyline(c, art, (1000 - art.width) // 2, y)
    y += art.height + 66
    draw_tracked(d, 500, y, "EDITORIAL WALL ART - PREMIUM PRINT", font(F_INTER_M, 22), 7, GRAY)
    draw_tracked(d, 500, 1500 - 120, "MERIDIANATLAS.CO", font(F_INTER_SB, 20), 6, BLACK)
    save_jpg(c, out / "pin-typo.jpg")


def pin_detail(artwork, meta, out):
    """Pin 2:3 full-bleed con crop di dettaglio DIVERSO da feed-detail
    (zoom e finestra differenti): terza variante visiva per la cadenza
    multi-board senza ripetere la stessa immagine."""
    band = 130
    img_h = 1500 - band
    det = crop_zoom(artwork, 1000, img_h, cx=0.42, cy=0.56, zoom=2.5)
    c = Image.new("RGB", (1000, 1500), IVORY)
    c.paste(det, (0, 0))
    d = ImageDraw.Draw(c)
    d.line([(0, img_h), (1000, img_h)], fill=HAIR, width=1)
    txt = f"THE DETAIL - {meta['city']} - NO. {meta['nn']}"
    f1 = fit_font(F_INTER_SB, txt, 900, 24, 15, tracking=6)
    asc, desc = f1.getmetrics()
    y = img_h + (band - (asc + desc) - 30) // 2
    y += draw_tracked(d, 500, y, txt, f1, 6, BLACK) + 10
    draw_tracked(d, 500, y, "MERIDIANATLAS.CO", font(F_INTER_M, 17), 5, GRAY)
    save_jpg(c, out / "pin-detail.jpg")


def pin_card(meta, out):
    """Card tipografica coordinate in formato pin 2:3: quarta variante
    visiva (solo tipografia, nessun artwork) distinta da pin-typo."""
    c = Image.new("RGB", (1000, 1500), IVORY)
    d = ImageDraw.Draw(c)
    f_over = font(F_INTER_M, 24)
    f_city = fit_font(F_PLAYFAIR, meta["city"], 860, 160, 76)
    f_country = font(F_INTER_M, 30)
    f_coords = font(F_INTER_R, 30)
    f_tag = font(F_INTER_M, 21)
    h_city = sum(f_city.getmetrics())
    block = 24 + 70 + h_city + 32 + 30 + 60 + 14 + 60 + 30 + 90 + 21
    y = (1500 - block) // 2 - 24
    y += draw_tracked(d, 500, y, f"CITY ATLAS - NO. {meta['nn']}", f_over, 9, GRAY) + 70
    y += draw_tracked(d, 500, y, meta["city"], f_city, 6, BLACK) + 32
    y += draw_tracked(d, 500, y, meta["country"], f_country, 12, BLACK) + 60
    diamond(d, 500, y + 7)
    y += 14 + 60
    y += draw_tracked(d, 500, y, meta["coords"], f_coords, 2, GRAY) + 90
    draw_tracked(d, 500, y, "EDITORIAL WALL ART - PREMIUM PRINT", f_tag, 7, BLACK)
    draw_tracked(d, 500, 1500 - 120, "MERIDIANATLAS.CO", font(F_INTER_SB, 20), 6, GRAY)
    save_jpg(c, out / "pin-card.jpg")


def reel(artwork_path, src, out):
    custom = src / "reel.mp4"
    target = out / "reel.mp4"
    if custom.exists():
        shutil.copy(custom, target)
        print("  ok  reel.mp4  (copiato da src - Higgsfield)")
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
        print(f"[{folder.name}]  skip: manca src/")
        return
    meta_p = src / "meta.json"
    if not meta_p.exists():
        print(f"[{folder.name}]  skip: manca meta.json")
        return
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    missing = [k for k in ("nn", "city", "country", "coords") if k not in meta]
    if missing:
        print(f"[{folder.name}]  skip: meta.json senza campi {missing}")
        return
    opts = {**DEFAULTS, **{k: meta[k] for k in DEFAULTS if k in meta}}

    art_p = find(src, "artwork")
    if not art_p:
        print(f"[{folder.name}]  skip: in attesa di src/artwork.(png|jpg)")
        return
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
    pin_detail(artwork, meta, folder)
    pin_card(meta, folder)
    reel(art_p, src, folder)
    build_site(folder.resolve().parents[2])


# ====================================================================== SITE =
SITE = "https://meridianatlas.co"
METRICOOL_PIXEL = '<img src="https://tracker.metricool.com/c3po.jpg?hash=44bdd722cca4b0fe96908e87b58222a9" alt="" width="1" height="1" loading="lazy" style="position:absolute;width:1px;height:1px;opacity:0"/>'

REDBUBBLE_LINKS = {
    "Amsterdam": "https://www.redbubble.com/shop/ap/180322890",
    "Barcelona": "https://www.redbubble.com/shop/ap/180322929",
    "Berlin": "https://www.redbubble.com/shop/ap/180342198",
    "Copenhagen": "https://www.redbubble.com/shop/ap/180342459",
    "Dublin": "https://www.redbubble.com/shop/ap/180342365",
    "Edinburgh": "https://www.redbubble.com/shop/ap/180342406",
    "Firenze": "https://www.redbubble.com/shop/ap/180344308",
    "Florence": "https://www.redbubble.com/shop/ap/180344308",
    "Kobenhavn": "https://www.redbubble.com/shop/ap/180342459",
    "København": "https://www.redbubble.com/shop/ap/180342459",
    "Lisboa": "https://www.redbubble.com/shop/ap/180326124",
    "Lisbon": "https://www.redbubble.com/shop/ap/180326124",
    "London": "https://www.redbubble.com/shop/ap/180319099",
    "Madrid": "https://www.redbubble.com/shop/ap/180342338",
    "Milan": "https://www.redbubble.com/shop/ap/180318106",
    "Milano": "https://www.redbubble.com/shop/ap/180318106",
    "Muenchen": "https://www.redbubble.com/shop/ap/180344162",
    "Munchen": "https://www.redbubble.com/shop/ap/180344162",
    "Munich": "https://www.redbubble.com/shop/ap/180344162",
    "München": "https://www.redbubble.com/shop/ap/180344162",
    "New York": "https://www.redbubble.com/shop/ap/180319187",
    "Paris": "https://www.redbubble.com/shop/ap/180319015",
    "Prague": "https://www.redbubble.com/shop/ap/180342300",
    "Praha": "https://www.redbubble.com/shop/ap/180342300",
    "Roma": "https://www.redbubble.com/shop/ap/180319218",
    "Rome": "https://www.redbubble.com/shop/ap/180319218",
    "San Francisco": "https://www.redbubble.com/shop/ap/180345075",
    "Stockholm": "https://www.redbubble.com/shop/ap/180342430",
    "Venezia": "https://www.redbubble.com/shop/ap/180343276",
    "Venice": "https://www.redbubble.com/shop/ap/180343276",
    "Vienna": "https://www.redbubble.com/shop/ap/180342272",
    "Wien": "https://www.redbubble.com/shop/ap/180342272"
}


def _city_key(value):
    value = str(value or "").strip().casefold()
    return "".join(ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch))


REDBUBBLE_LINKS_BY_KEY = {_city_key(city): url for city, url in REDBUBBLE_LINKS.items()}


def redbubble_url_for_city(city):
    return REDBUBBLE_LINKS_BY_KEY.get(_city_key(city), "")


def _e(value):
    return html_lib.escape(str(value or ""), quote=True)


def _abs(path):
    path = str(path or "")
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/"):
        path = "/" + path
    return SITE + path


def _asset(slug, filename):
    return f"/assets/social/{slug}/{filename}"


ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]

GOOGLE_FONTS = ("https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,700"
                "&family=Inter:wght@400;500;600;800&display=swap")

GRAIN = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E"
         "%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' "
         "stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")

COMPASS = ('<svg class="compass" viewBox="0 0 40 40" width="34" height="34" aria-hidden="true" focusable="false">'
           '<circle cx="20" cy="20" r="18.5" fill="none" stroke="currentColor" stroke-width="1"/>'
           '<circle cx="20" cy="20" r="13" fill="none" stroke="currentColor" stroke-width=".6" opacity=".45"/>'
           '<path d="M20 3.5 22.6 20 20 36.5 17.4 20Z" fill="#9C7A3C"/>'
           '<path d="M3.5 20 20 17.4 36.5 20 20 22.6Z" fill="currentColor" opacity=".8"/>'
           '<circle cx="20" cy="20" r="1.7" fill="#F2EDE2" stroke="currentColor" stroke-width=".9"/></svg>')

DIAMOND = '<span class="dia" aria-hidden="true">&#9670;</span>'

# --------------------------------------------------------------------- css --
CSS = """
:root{
  --paper:#F2EDE2;--paper-2:#ECE4D1;--ink:#1A1A1A;--sepia:#6A6253;
  --line:rgba(26,26,26,.22);--line-soft:rgba(26,26,26,.12);
  --sage:#7A8B73;--blue:#BCD2DE;--brass:#9C7A3C;
  --serif:'Playfair Display',Georgia,'Times New Roman',serif;
  --sans:Inter,Helvetica,Arial,sans-serif;
  --rail:34px;--max:1180px;--pad:clamp(24px,4.5vw,56px);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
html,body{margin:0;padding:0;max-width:100%;overflow-x:clip}
body{
  background:var(--paper);color:var(--ink);font-family:var(--sans);
  font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased;
  padding-left:var(--rail);
}
body::after{ /* grana carta */
  content:"";position:fixed;inset:0;z-index:4;pointer-events:none;
  background:url("GRAIN_URI");background-size:160px;opacity:.05;mix-blend-mode:multiply;
}
::selection{background:var(--blue);color:var(--ink)}
img,video{display:block;max-width:100%;height:auto}
a{color:inherit;text-decoration:none}
.wrap{width:min(var(--max),100%);margin-inline:auto;padding-inline:var(--pad)}
.skip{position:absolute;left:-999px;top:10px;background:var(--ink);color:var(--paper);padding:10px 16px;z-index:40}
.skip:focus{left:calc(var(--rail) + 10px)}
:focus-visible{outline:2px solid var(--brass);outline-offset:4px}
.dia{color:var(--brass);font-size:.62em;vertical-align:.18em;margin-inline:.15em}

/* ------------------------------------------------ meridiano (firma) ----- */
.meridian{
  position:fixed;inset:0 auto 0 0;width:var(--rail);z-index:30;
  border-right:1px solid var(--line);background:var(--paper);
}
.meridian::before{ /* graduazioni */
  content:"";position:absolute;inset:0;
  background:
    repeating-linear-gradient(to bottom,var(--line) 0 1px,transparent 1px 64px) right top/16px 100% no-repeat,
    repeating-linear-gradient(to bottom,var(--line-soft) 0 1px,transparent 1px 16px) right top/9px 100% no-repeat;
}
.meridian b{
  position:absolute;left:0;right:0;text-align:center;
  font:800 9px/1 var(--sans);letter-spacing:.22em;color:var(--sepia);
}
.meridian b:first-of-type{top:10px}
.meridian b:last-of-type{bottom:10px}
.meridian i{ /* ago in ottone */
  position:absolute;top:26px;left:50%;width:11px;height:11px;display:none;
  background:var(--brass);transform:translateX(-50%) rotate(45deg);
  box-shadow:0 0 0 2px var(--paper);
}
.voyage{position:fixed;top:0;left:0;right:0;height:3px;z-index:31;display:none;
  background:var(--brass);transform-origin:0 50%;transform:scaleX(0)}
@supports (animation-timeline: scroll()){
  @media (prefers-reduced-motion:no-preference){
    .meridian i{display:block;animation:southward linear both;animation-timeline:scroll(root)}
    @keyframes southward{to{top:calc(100% - 37px)}}
    .voyage{animation:voyage linear both;animation-timeline:scroll(root)}
    @keyframes voyage{to{transform:scaleX(1)}}
  }
}

/* ------------------------------------------------------------ header ---- */
.site-header{
  position:sticky;top:0;z-index:20;
  background:color-mix(in srgb,var(--paper) 96%,transparent);
  backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
  border-bottom:1px solid var(--line);
}
.nav{min-height:74px;display:flex;align-items:center;justify-content:space-between;gap:20px}
.brand{font:800 12px/1.3 var(--sans);letter-spacing:.34em;text-transform:uppercase;white-space:nowrap}
.brand small{display:block;font-weight:600;font-size:8px;letter-spacing:.4em;color:var(--sepia);margin-top:4px}
.nav-links{display:flex;gap:26px;flex-wrap:wrap}
.nav-links a{font:800 10px/1 var(--sans);letter-spacing:.24em;text-transform:uppercase;color:var(--sepia);
  padding:6px 0;border-bottom:1px solid transparent}
.nav-links a:hover{color:var(--ink);border-bottom-color:var(--brass)}

/* ---------------------------------------------------------- testo base -- */
.eyebrow{font:800 10.5px/1.4 var(--sans);letter-spacing:.32em;text-transform:uppercase;color:var(--sepia);margin:0}
.kicker{display:flex;align-items:center;gap:16px}
.kicker::after{content:"";height:1px;flex:1;max-width:170px;background:var(--line)}
h1,h2{text-wrap:balance}
.btn{
  display:inline-flex;align-items:center;justify-content:center;gap:10px;
  min-height:50px;padding:14px 26px;border:1.4px solid var(--ink);
  font:800 11px/1 var(--sans);letter-spacing:.2em;text-transform:uppercase;
  background:transparent;transition:transform .16s ease,background .16s ease,color .16s ease;
}
.btn.primary{background:var(--ink);color:var(--paper)}
.btn:hover{transform:translateY(-1px)}
.btn.primary:hover{background:transparent;color:var(--ink)}
.btn.muted{border-color:var(--line);color:var(--sepia)}

/* -------------------------------------------------- cornice da tavola --- */
.plate-frame{position:relative;background:var(--paper);border:1px solid var(--ink);padding:15px}
.plate-frame::before{content:"";position:absolute;inset:7px;border:1px solid var(--line);pointer-events:none}
.plate-frame::after{ /* tacche di graduazione della cornice */
  content:"";position:absolute;inset:0;pointer-events:none;opacity:.6;
  background:
    repeating-linear-gradient(90deg,var(--ink) 0 1px,transparent 1px 18px) left top/100% 6px,
    repeating-linear-gradient(90deg,var(--ink) 0 1px,transparent 1px 18px) left bottom/100% 6px,
    repeating-linear-gradient(0deg,var(--ink) 0 1px,transparent 1px 18px) left top/6px 100%,
    repeating-linear-gradient(0deg,var(--ink) 0 1px,transparent 1px 18px) right top/6px 100%;
  background-repeat:no-repeat;
}
.plate-frame img,.plate-frame video{border:1px solid var(--ink);width:100%;background:var(--paper-2)}
.fig video{aspect-ratio:4/5;object-fit:cover;height:auto}
.folio{
  display:flex;justify-content:space-between;gap:14px;margin-top:13px;
  font:800 10px/1.5 var(--sans);letter-spacing:.24em;text-transform:uppercase;color:var(--sepia);
}
.folio b{color:var(--ink)}

/* ------------------------------------------------------- frontespizio --- */
.hero{padding-block:clamp(48px,8vw,100px) clamp(44px,7vw,84px)}
.hero-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,440px);
  gap:clamp(34px,6vw,80px);align-items:center}
.hero h1{
  font-family:var(--serif);font-weight:700;font-style:italic;
  font-size:clamp(54px,8.6vw,116px);line-height:.96;letter-spacing:.005em;margin:22px 0 0;
}
.hero h1 .rm{font-style:normal;letter-spacing:.02em}
.lead{font-size:clamp(17px,1.9vw,20px);line-height:1.7;color:#43403A;margin:26px 0 0;max-width:600px}
.hero-actions{display:flex;gap:14px;flex-wrap:wrap;margin-top:34px}
.edition{
  margin-top:30px;padding:14px 0 0;border-top:1px solid var(--line);max-width:560px;
  font-size:13.5px;color:var(--sepia);display:flex;gap:14px;align-items:flex-start;
}
.edition .compass{flex:none;color:var(--ink)}

/* ----------------------------------------------------------- ticker ----- */
.ticker{overflow:hidden;border-block:1px solid var(--line);background:var(--paper-2);padding:13px 0}
.ticker-track{display:flex;gap:0;width:max-content;animation:tick 46s linear infinite}
.ticker span{font:800 10.5px/1 var(--sans);letter-spacing:.3em;text-transform:uppercase;
  color:var(--sepia);white-space:nowrap;padding-right:34px}
.ticker .dia{margin-right:34px}
@keyframes tick{to{transform:translateX(-50%)}}
@media (prefers-reduced-motion:reduce){.ticker-track{animation:none;flex-wrap:wrap;white-space:normal}}

/* ----------------------------------------------------------- sezioni ---- */
.section{padding-block:clamp(58px,8vw,100px);border-top:1px solid var(--line);scroll-margin-top:92px}
.section-head{display:grid;grid-template-columns:minmax(0,1fr) minmax(260px,400px);
  gap:30px;align-items:end;margin-bottom:clamp(34px,5vw,52px)}
.section-head h2{font-family:var(--serif);font-weight:700;
  font-size:clamp(34px,4.8vw,56px);line-height:1.05;letter-spacing:.02em;margin:12px 0 0}
.section-head p{color:#514C44;margin:0;font-size:15.5px}

/* --------------------------------------------------- griglia tavole ----- */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(215px,1fr));gap:44px 30px}
.card a{display:block;position:relative}
.card .plate{width:100%;aspect-ratio:2/3;object-fit:cover;border:1.4px solid var(--ink);
  background:var(--paper-2);transition:transform .22s ease,box-shadow .22s ease}
.card a::after{ /* crocini di registro all'hover */
  content:"";position:absolute;inset:-9px;pointer-events:none;opacity:0;transition:opacity .2s ease;
  background:
    linear-gradient(var(--brass),var(--brass)) left 0 top 0/15px 1.5px,
    linear-gradient(var(--brass),var(--brass)) left 0 top 0/1.5px 15px,
    linear-gradient(var(--brass),var(--brass)) right 0 top 0/15px 1.5px,
    linear-gradient(var(--brass),var(--brass)) right 0 top 0/1.5px 15px,
    linear-gradient(var(--brass),var(--brass)) left 0 bottom 0/15px 1.5px,
    linear-gradient(var(--brass),var(--brass)) left 0 bottom 0/1.5px 15px,
    linear-gradient(var(--brass),var(--brass)) right 0 bottom 0/15px 1.5px,
    linear-gradient(var(--brass),var(--brass)) right 0 bottom 0/1.5px 15px;
  background-repeat:no-repeat;
}
.card a:hover .plate{transform:translateY(-4px);box-shadow:0 20px 44px rgba(26,26,26,.14)}
.card a:hover::after{opacity:1}
.card figcaption{text-align:center;margin-top:15px}
.card .no{font:800 10px/1.4 var(--sans);letter-spacing:.3em;text-transform:uppercase;color:var(--sepia)}
.card .name{font-family:var(--serif);font-size:23px;font-weight:700;letter-spacing:.05em;margin-top:5px}
.card .coords{font-size:11px;letter-spacing:.12em;color:var(--sepia);margin-top:5px;font-variant-numeric:tabular-nums}
@supports (animation-timeline: view()){
  @media (prefers-reduced-motion:no-preference){
    .card{animation:surface .6s ease both;animation-timeline:view();animation-range:entry 0% entry 38%}
    @keyframes surface{from{opacity:0;transform:translateY(26px)}}
  }
}

/* --------------------------------------------- indice delle tavole ------ */
.plate-index{list-style:none;margin:0;padding:0;columns:2;column-gap:70px}
.plate-index li{break-inside:avoid}
.plate-index a{display:flex;align-items:baseline;gap:12px;padding:11px 2px;border-bottom:1px solid var(--line-soft)}
.plate-index .city{font-family:var(--serif);font-weight:700;font-size:21px;letter-spacing:.04em}
.plate-index .dots{flex:1;border-bottom:2px dotted var(--line);transform:translateY(-5px);min-width:30px}
.plate-index .no{font:800 11px/1 var(--sans);letter-spacing:.2em;color:var(--sepia);font-variant-numeric:tabular-nums;white-space:nowrap}
.plate-index a:hover .city{color:var(--brass)}
.plate-index a:hover .no{color:var(--ink)}

/* ----------------------------------------------------------- processo --- */
.method{display:grid;grid-template-columns:repeat(3,1fr);gap:0;border:1px solid var(--line)}
.method article{padding:30px 28px 34px;border-left:1px solid var(--line)}
.method article:first-child{border-left:0}
.method .rn{font-family:var(--serif);font-style:italic;font-weight:700;font-size:44px;color:var(--brass);line-height:1}
.method h3{font-family:var(--serif);font-size:25px;line-height:1.15;letter-spacing:.02em;margin:14px 0 10px}
.method p{margin:0;color:#514C44;font-size:14.5px}

/* ----------------------------------------------------------- epigrafe --- */
.quote{font-family:var(--serif);font-style:italic;font-weight:700;
  font-size:clamp(28px,4.4vw,50px);line-height:1.2;text-align:center;max-width:880px;margin:0 auto}
.quote small{display:block;font:800 10.5px/1 var(--sans);font-style:normal;
  letter-spacing:.3em;text-transform:uppercase;color:var(--sepia);margin-top:26px}

/* -------------------------------------------------------- pagina citta -- */
.breadcrumb{font:800 10.5px/1.6 var(--sans);letter-spacing:.22em;text-transform:uppercase;color:var(--sepia);margin:0 0 26px}
.breadcrumb a:hover{color:var(--brass)}
.city-hero{padding-block:clamp(44px,7vw,82px)}
.city-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,520px);
  gap:clamp(32px,6vw,72px);align-items:start}
.city-grid h1{font-family:var(--serif);font-weight:700;
  font-size:clamp(56px,8.8vw,116px);line-height:.95;letter-spacing:.02em;margin:16px 0 0}
.meta-line{display:flex;gap:18px;flex-wrap:wrap;margin-top:22px;color:var(--sepia);
  font:800 11.5px/1.6 var(--sans);letter-spacing:.18em;text-transform:uppercase;font-variant-numeric:tabular-nums}
.story{font-size:17.5px;line-height:1.8;color:#43403A;margin:28px 0 0;max-width:640px}
.story::first-letter{
  font-family:var(--serif);font-weight:700;float:left;
  font-size:3.6em;line-height:.82;padding:6px 12px 0 0;color:var(--ink);
}
@supports (initial-letter:3){
  .story::first-letter{float:none;font-size:inherit;padding:0 .12em 0 0;initial-letter:3;-webkit-initial-letter:3}
}
.record{border:1px solid var(--line);background:var(--paper-2);padding:26px;margin-top:34px;max-width:640px}
.record h2{font:800 10.5px/1 var(--sans);letter-spacing:.3em;text-transform:uppercase;color:var(--sepia);margin:0 0 18px}
.record dl{display:grid;grid-template-columns:128px 1fr;gap:11px 20px;margin:0}
.record dt{font:800 10.5px/1.7 var(--sans);letter-spacing:.2em;text-transform:uppercase;color:var(--sepia)}
.record dd{font-size:14px;margin:0}
.record .note{font-size:12.5px;color:var(--sepia);margin:18px 0 0}

/* ----------------------------------------------------------- galleria --- */
.gallery{display:grid;grid-template-columns:repeat(2,1fr);gap:clamp(26px,4vw,44px)}
.fig{margin:0}
.fig figcaption{margin-top:12px;font:800 10.5px/1.6 var(--sans);letter-spacing:.22em;text-transform:uppercase;color:var(--sepia)}
.fig figcaption .rn{font-family:var(--serif);font-style:italic;font-weight:700;
  font-size:17px;letter-spacing:0;text-transform:none;color:var(--brass);margin-right:9px}
.zoomable{cursor:zoom-in}

/* ------------------------------------------------------ sfoglia tavole -- */
.leaf{display:grid;grid-template-columns:1fr auto 1fr;gap:16px;align-items:center;
  border:1px solid var(--line);margin-top:clamp(40px,6vw,64px)}
.leaf a{padding:22px 24px;display:block}
.leaf a:hover .name{color:var(--brass)}
.leaf .dir{display:block;font:800 9.5px/1.6 var(--sans);letter-spacing:.28em;text-transform:uppercase;color:var(--sepia)}
.leaf .name{display:block;font-family:var(--serif);font-weight:700;font-size:21px;letter-spacing:.03em;margin-top:4px}
.leaf .next{text-align:right;border-left:1px solid var(--line)}
.leaf .home{padding:22px 18px;border-left:1px solid var(--line);color:var(--sepia)}
.leaf .home:hover{color:var(--brass)}

/* ----------------------------------------------------------- lightbox --- */
.lightbox{border:1px solid var(--ink);padding:14px;background:var(--paper);max-width:min(92vw,860px)}
.lightbox::backdrop{background:rgba(26,26,26,.62);backdrop-filter:blur(3px)}
.lightbox img{border:1px solid var(--ink);max-height:82vh;width:auto;max-width:100%;margin:auto}
.lb-x{position:absolute;top:8px;right:8px;width:38px;height:38px;border:1px solid var(--ink);
  background:var(--paper);font:400 19px/1 var(--sans);cursor:pointer}
.lb-x:hover{background:var(--ink);color:var(--paper)}

/* ------------------------------------------------------------- footer --- */
.footer{border-top:1px solid var(--line);padding:44px 0 64px;text-align:center}
.footer .compass{margin:0 auto 18px;color:var(--ink)}
.footer p{font-size:12.5px;letter-spacing:.08em;color:var(--sepia);margin:5px 0}
.footer .colophon{font-size:11px;letter-spacing:.14em;text-transform:uppercase;margin-top:16px}

/* ---------------------------------------------------- view transitions -- */
@media (prefers-reduced-motion:no-preference){
  @view-transition{navigation:auto}
}
::view-transition-old(root),::view-transition-new(root){animation-duration:.34s}

/* --------------------------------------------------------- responsive --- */
@media(max-width:980px){
  body{padding-left:0}
  .meridian{display:none}
  .voyage{display:block}
  .skip:focus{left:10px}
  .hero-grid,.city-grid,.section-head{grid-template-columns:1fr}
  .hero-art-col{max-width:430px;margin-inline:auto;width:100%}
  .method{grid-template-columns:1fr;border-left:0;border-right:0}
  .method article{border-left:0;border-top:1px solid var(--line)}
  .method article:first-child{border-top:0}
  .plate-index{columns:1}
  .city-grid .plate-frame{max-width:540px;margin-inline:auto}
}
@media(max-width:640px){
  .brand{letter-spacing:.22em;font-size:11px}
  .nav{flex-wrap:wrap;padding-block:14px;min-height:0}
  .nav-links{gap:18px}
  .hero{padding-top:40px}
  .hero-actions{display:grid}
  .btn{width:100%}
  .grid{grid-template-columns:1fr 1fr;gap:32px 18px}
  .gallery{grid-template-columns:1fr}
  .record dl{grid-template-columns:1fr;gap:4px 0}
  .record dt{margin-top:10px}
  .leaf{grid-template-columns:1fr 1fr}
  .leaf .home{display:none}
  .leaf .next{border-left:1px solid var(--line)}
}
@media (prefers-reduced-motion:reduce){
  html{scroll-behavior:auto}
  .btn,.card .plate,.card a::after{transition:none}
  .card{animation:none}
}
""".replace("GRAIN_URI", GRAIN).strip() + "\n"

# ----------------------------------------------------------------- js ------
SPECULATION = ('<script type="speculationrules">'
               '{"prerender":[{"where":{"href_matches":"/ma-*"},"eagerness":"moderate"}]}'
               '</script>')

LIGHTBOX = ('<dialog class="lightbox" id="lb">'
            '<button class="lb-x" aria-label="Close enlarged view">&times;</button>'
            '<img alt=""></dialog>'
            '<script>(function(){var d=document.getElementById("lb");if(!d||!d.showModal)return;'
            'var im=d.querySelector("img");'
            'document.querySelectorAll(".zoomable").forEach(function(el){'
            'el.addEventListener("click",function(){im.src=el.currentSrc||el.src;im.alt=el.alt||"";d.showModal()})});'
            'd.addEventListener("click",function(e){if(e.target===d||e.target.classList.contains("lb-x"))d.close()});'
            'd.addEventListener("close",function(){im.src=""})})();</script>')

RM_JS = ('<script>if(matchMedia("(prefers-reduced-motion: reduce)").matches)'
         'document.querySelectorAll("video[autoplay]").forEach(function(v){v.removeAttribute("autoplay");v.pause()})'
         '</script>')

MERIDIAN_HTML = ('<div class="meridian" aria-hidden="true"><b>N</b><i></i><b>S</b></div>'
                 '<div class="voyage" aria-hidden="true"></div>')


# --------------------------------------------------------------- frame ------
def _head(title, desc, og_image, canonical, css_href, schemas=None, preload=None):
    title_e, desc_e = _e(title), _e(desc)
    canonical_e, og_e = _e(canonical), _e(_abs(og_image))
    base = {"@context": "https://schema.org", "@type": "Organization",
            "name": "Meridian Atlas Co.", "url": SITE,
            "description": "Editorial, AI-created city map prints for considered interiors.",
            "email": "studio@meridianatlas.co"}
    blocks = [base] + (schemas or [])
    schema_json = json.dumps(blocks if len(blocks) > 1 else blocks[0], ensure_ascii=False)
    preload_tag = (f'  <link rel="preload" as="image" href="{_e(preload)}" fetchpriority="high">\n'
                   if preload else "")
    return (f'<!doctype html>\n<html lang="en">\n<head>\n'
            f'  <meta charset="utf-8">\n'
            f'  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'  <title>{title_e}</title>\n'
            f'  <meta name="description" content="{desc_e}">\n'
            f'  <meta name="theme-color" content="#F2EDE2">\n'
            f'  <link rel="canonical" href="{canonical_e}">\n'
            f'  <meta property="og:type" content="website">\n'
            f'  <meta property="og:site_name" content="Meridian Atlas Co.">\n'
            f'  <meta property="og:title" content="{title_e}">\n'
            f'  <meta property="og:description" content="{desc_e}">\n'
            f'  <meta property="og:image" content="{og_e}">\n'
            f'  <meta property="og:url" content="{canonical_e}">\n'
            f'  <meta name="twitter:card" content="summary_large_image">\n'
            f'  <link rel="preconnect" href="https://fonts.googleapis.com">\n'
            f'  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            f'  <link rel="stylesheet" href="{_e(GOOGLE_FONTS)}">\n'
            f'  <link rel="stylesheet" href="{_e(css_href)}">\n'
            f'{preload_tag}'
            f'  <script type="application/ld+json">{schema_json}</script>\n'
            f'</head>\n')


def _header():
    return ('<a class="skip" href="#content">Skip to content</a>'
            + MERIDIAN_HTML +
            '<header class="site-header"><div class="wrap nav">'
            '<a class="brand" href="/">Meridian Atlas Co.<small>Editorial city plates</small></a>'
            '<nav class="nav-links" aria-label="Main navigation">'
            '<a href="/#collection">Collection</a><a href="/#index">Index</a><a href="/#method">Method</a>'
            '</nav></div></header>')


def _footer(count=None):
    edition = (f'<p class="colophon">An atlas of {count} numbered plate{"s" if count != 1 else ""} &middot; new cities added through the year</p>'
               if count else "")
    return ('<footer class="footer"><div class="wrap">'
            + COMPASS +
            '<p>Every plate is an AI-created artwork, refined by hand and prepared for archival printing.</p>'
            '<p>&copy; Meridian Atlas Co. &mdash; Editorial wall art for the cities you love.</p>'
            + edition +
            '<p class="colophon">Set in Playfair Display &amp; Inter &middot; printed on demand via Redbubble</p>'
            '</div></footer>')


def _page_end(count=None):
    return _footer(count) + LIGHTBOX + METRICOOL_PIXEL + RM_JS + SPECULATION + '</body></html>'


def _live_cities(root: Path):
    out = []
    for meta_p in sorted(root.glob("assets/social/ma-*/src/meta.json")):
        folder = meta_p.parent.parent
        if not (folder / "feed-artwork.jpg").exists():
            continue
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        meta["_slug"] = folder.name
        mockups = [p.name for p in sorted(folder.glob("*-feed.jpg"))
                   if p.name not in {"feed-artwork.jpg", "feed-detail.jpg", "feed-card.jpg"}]
        meta["_mockup_feed"] = mockups[0] if mockups else ""
        meta["_has_mockup"] = bool(mockups)
        meta["_has_reel"] = (folder / "reel.mp4").exists()
        meta["_redbubble"] = (meta.get("redbubble") or redbubble_url_for_city(meta.get("city"))).strip()
        out.append(meta)
    return sorted(out, key=lambda m: str(m["nn"]).zfill(4))


def _cta_html(m):
    rb = (m.get("_redbubble") or m.get("redbubble") or redbubble_url_for_city(m.get("city"))).strip()
    if not rb:
        return '<span class="btn muted" aria-disabled="true">Print available soon</span>'
    sep = "&" if "?" in rb else "?"
    href = f"{rb}{sep}utm_source=site&utm_medium=site&utm_campaign={m['_slug']}"
    return f'<a class="btn primary" href="{_e(href)}" target="_blank" rel="noopener">View the print</a>'


# --------------------------------------------------------------- pagine ----
def _city_page(m, prev_m, next_m, count):
    slug, nn, city = m["_slug"], str(m["nn"]), m["city"]
    country, coords = m.get("country", ""), m.get("coords", "")
    desc = m.get("story") or (f"An editorial, AI-created map of {city} — plate No. {nn} in the "
                              f"City Atlas — drawn in sage, dusty blue and warm ivory and prepared "
                              f"for archival printing.")
    canonical = f"{SITE}/{slug}/"
    of_n = f" of {count}" if count > 1 else ""
    artwork = _asset(slug, "feed-artwork.jpg")
    detail = _asset(slug, "feed-detail.jpg")
    card = _asset(slug, "feed-card.jpg")
    reel = _asset(slug, "reel.mp4")
    mockup = _asset(slug, m["_mockup_feed"]) if m.get("_mockup_feed") else ""
    vt = f"plate-{slug}"

    schemas = [
        {"@type": "Product", "name": f"{city} City Atlas Print No. {nn}",
         "brand": {"@type": "Brand", "name": "Meridian Atlas Co."},
         "image": _abs(artwork), "description": desc, "url": canonical},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "The Atlas", "item": f"{SITE}/"},
            {"@type": "ListItem", "position": 2, "name": f"{city} — No. {nn}", "item": canonical}]},
    ]

    figs, fig_i = [], 0
    def fig(media, caption):
        nonlocal fig_i
        rn = ROMAN[fig_i] if fig_i < len(ROMAN) else str(fig_i + 1)
        fig_i += 1
        return (f'<figure class="fig"><div class="plate-frame">{media}</div>'
                f'<figcaption><span class="rn">Fig. {rn}</span>{_e(caption)}</figcaption></figure>')

    figs.append(fig(f'<img class="zoomable" src="{_e(detail)}" alt="{_e(city)} map detail, close crop of the street grid" width="1080" height="1350" loading="lazy">', "Map detail"))
    if mockup:
        figs.append(fig(f'<img class="zoomable" src="{_e(mockup)}" alt="{_e(city)} framed map print shown in an interior" width="1080" height="1350" loading="lazy">', "Interior scale"))
    figs.append(fig(f'<img class="zoomable" src="{_e(card)}" alt="{_e(city)} typographic plate with coordinates" width="1080" height="1350" loading="lazy">', "Coordinates plate"))
    if m.get("_has_reel"):
        figs.append(fig(f'<video autoplay muted loop playsinline preload="metadata" poster="{_e(artwork)}" src="{_e(reel)}" width="1080" height="1920"></video>', "Motion preview"))

    def leaf_link(c, cls, label):
        return (f'<a class="{cls}" href="/{_e(c["_slug"])}/"><span class="dir">{label}</span>'
                f'<span class="name">No. {_e(c["nn"])} &mdash; {_e(c["city"])}</span></a>')

    leaf = ""
    if count > 1:
        leaf = ('<nav class="leaf" aria-label="Leaf through the atlas">'
                + leaf_link(prev_m, "prev", "&larr; Previous plate")
                + '<a class="home" href="/#index" aria-label="Index of plates">' + COMPASS + '</a>'
                + leaf_link(next_m, "next", "Next plate &rarr;")
                + '</nav>')

    return (_head(f"{city} Map Print — City Atlas No. {nn} | Meridian Atlas Co.",
                  desc, artwork, canonical, "../style.css", schemas, preload=artwork)
        + '<body>' + _header()
        + '<main id="content" class="wrap">'
        + '<section class="city-hero">'
        + f'<p class="breadcrumb"><a href="/">The Atlas</a> &nbsp;&middot;&nbsp; Plate No. {_e(nn)}{of_n}</p>'
        + '<div class="city-grid"><div>'
        + f'<p class="eyebrow">City Atlas &mdash; No. {_e(nn)}</p>'
        + f'<h1>{_e(city)}</h1>'
        + f'<div class="meta-line"><span>{_e(country)}</span><span class="dia" aria-hidden="true">&#9670;</span><span>{_e(coords)}</span></div>'
        + f'<p class="story">{_e(desc)}</p>'
        + '<div class="hero-actions" style="margin-top:30px">' + _cta_html(m)
        + '<a class="btn" href="/#collection">All plates</a></div>'
        + '<aside class="record"><h2>Plate record</h2><dl>'
        + f'<dt>Series</dt><dd>City Atlas &mdash; No. {_e(nn)}{of_n}</dd>'
        + '<dt>Palette</dt><dd>Sage, dusty blue and warm ivory on editorial black</dd>'
        + '<dt>Method</dt><dd>AI-created artwork, refined by hand and prepared for print</dd>'
        + f'<dt>Coordinates</dt><dd>{_e(coords)}</dd>'
        + '</dl><p class="note">Sizes, papers and final print options are managed on Redbubble.</p></aside>'
        + '</div>'
        + f'<figure class="plate-frame" style="view-transition-name:{vt}">'
        + f'<img src="{_e(artwork)}" alt="{_e(city)} editorial city map print, City Atlas No. {_e(nn)}" width="1080" height="1350" fetchpriority="high">'
        + '</figure></div></section>'
        + '<section class="section"><div class="section-head"><div>'
        + '<p class="eyebrow">The figures</p><h2>One plate, studied four ways.</h2></div>'
        + '<p>Tap any figure to enlarge it. Each study shows how the plate behaves: as a map, in a room, as typography and in motion.</p></div>'
        + f'<div class="gallery">{"".join(figs)}</div>'
        + leaf
        + '</section></main>' + _page_end(count))


def _index_page(cities):
    count = len(cities)
    first = cities[0] if cities else None
    latest = cities[-1] if cities else None
    og = _asset(first["_slug"], "feed-artwork.jpg") if first else "/"

    schemas = [{"@type": "ItemList", "name": "City Atlas — numbered plates",
                "itemListElement": [
                    {"@type": "ListItem", "position": i + 1,
                     "name": f'{m["city"]} — No. {m["nn"]}', "url": f'{SITE}/{m["_slug"]}/'}
                    for i, m in enumerate(cities)]}]

    cards = "".join(
        f'<figure class="card"><a href="/{_e(m["_slug"])}/">'
        f'<img class="plate" src="{_e(_asset(m["_slug"], "pin-typo.jpg"))}" '
        f'alt="{_e(m["city"])} map print — City Atlas No. {_e(m["nn"])}" '
        f'width="1000" height="1500" loading="lazy" style="view-transition-name:plate-{_e(m["_slug"])}">'
        f'<figcaption><div class="no">Plate No. {_e(m["nn"])}</div>'
        f'<div class="name">{_e(m["city"])}</div>'
        f'<div class="coords">{_e(m.get("coords", ""))}</div></figcaption></a></figure>'
        for m in cities)

    index_rows = "".join(
        f'<li><a href="/{_e(m["_slug"])}/"><span class="city">{_e(m["city"])}</span>'
        f'<span class="dots" aria-hidden="true"></span><span class="no">No. {_e(m["nn"])}</span></a></li>'
        for m in cities)

    featured = ""
    if first:
        featured = ('<div class="hero-art-col"><figure class="plate-frame">'
                    f'<img src="{_e(_asset(first["_slug"], "feed-artwork.jpg"))}" '
                    f'alt="Featured plate: {_e(first["city"])}, City Atlas No. {_e(first["nn"])}" '
                    f'width="1080" height="1350" fetchpriority="high">'
                    '</figure></div>')

    ticker_items = "".join(
        f'<span>{_e(m["city"])} No. {_e(m["nn"])}</span><span class="dia" aria-hidden="true">&#9670;</span>'
        for m in cities[:12]) + '<span>AI-created editorial wall art</span><span class="dia" aria-hidden="true">&#9670;</span>'
    latest_name = latest.get("city") if latest else "new cities"

    return (_head("Meridian Atlas Co. — Editorial City Map Prints",
                  "A numbered atlas of AI-created city map prints in sage, dusty blue and warm ivory — quiet, editorial wall art for the cities you love.",
                  og, f"{SITE}/", "style.css", schemas,
                  preload=_asset(first["_slug"], "feed-artwork.jpg") if first else None)
        + '<body>' + _header() + '<main id="content">'
        + '<section class="hero wrap"><div class="hero-grid"><div>'
        + '<div class="kicker"><p class="eyebrow">City Atlas &mdash; a numbered collection</p></div>'
        + '<h1>Quiet maps for <span class="rm">places that stay.</span></h1>'
        + '<p class="lead">Meridian Atlas Co. turns the cities you love into restrained, editorial wall art: '
        + 'true street grids, exact coordinates and a calm palette of sage, dusty blue and warm ivory, '
        + 'composed like the plates of a vintage atlas.</p>'
        + '<div class="hero-actions"><a class="btn primary" href="#collection">View the collection</a>'
        + '<a class="btn" href="#method">How plates are made</a></div>'
        + f'<p class="edition">{COMPASS}<span>{count} plate{"s" if count != 1 else ""} published to date &middot; latest release: '
        + f'{_e(latest_name)}. Every artwork is AI-created, refined by hand and numbered as part of one continuous atlas.</span></p>'
        + '</div>' + featured + '</div></section>'
        + f'<div class="ticker" aria-hidden="true"><div class="ticker-track"><span style="display:contents">{ticker_items}</span><span style="display:contents">{ticker_items}</span></div></div>'
        + '<section id="collection" class="wrap section"><div class="section-head"><div>'
        + '<p class="eyebrow">The collection</p><h2>A collectible plate for every city.</h2></div>'
        + '<p>Browse the numbered series. Each city opens as its own plate, with artwork studies, interior scale and a direct path to the print.</p></div>'
        + f'<div class="grid">{cards}</div></section>'
        + '<section id="index" class="wrap section"><div class="section-head"><div>'
        + '<p class="eyebrow">Index of plates</p><h2>Find your city.</h2></div>'
        + '<p>The atlas grows through the year. If your city is not listed yet, it may already be on the route.</p></div>'
        + f'<ol class="plate-index">{index_rows}</ol></section>'
        + '<section id="method" class="wrap section"><div class="section-head"><div>'
        + '<p class="eyebrow">Method</p><h2>How a plate is made.</h2></div>'
        + '<p>Three steps stand between a city and its place on your wall — the same sequence, for every plate in the atlas.</p></div>'
        + '<div class="method">'
        + '<article><div class="rn">I.</div><h3>The city is drawn</h3><p>An AI-created map composition captures the real street grid, parks, rails and water in the atlas palette.</p></article>'
        + '<article><div class="rn">II.</div><h3>The plate is refined</h3><p>Each artwork is reviewed and corrected by hand, then numbered, titled with its local name and set with exact coordinates.</p></article>'
        + '<article><div class="rn">III.</div><h3>The print is made</h3><p>Plates are prepared at archival resolution and printed on demand via Redbubble, in the size and paper you choose.</p></article>'
        + '</div></section>'
        + '<section class="wrap section"><p class="quote">&ldquo;A calm atlas for modern interiors &mdash; city memories translated into quiet, architectural wall art.&rdquo;<small>Meridian Atlas Co.</small></p></section>'
        + '</main>' + _page_end(count))


def build_site(root: Path):
    cities = _live_cities(root)
    if not cities:
        print("  --  sito: nessuna citta' pubblicata, salto")
        return
    (root / "style.css").write_text(CSS, encoding="utf-8")
    (root / "index.html").write_text(_index_page(cities), encoding="utf-8")
    urls = [f"{SITE}/"]
    n = len(cities)
    for i, m in enumerate(cities):
        prev_m, next_m = cities[(i - 1) % n], cities[(i + 1) % n]
        d = root / m["_slug"]
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(_city_page(m, prev_m, next_m, n), encoding="utf-8")
        urls.append(f"{SITE}/{m['_slug']}/")
    from datetime import date as _date
    today = _date.today().isoformat()
    sm = ('<?xml version="1.0" encoding="UTF-8"?>'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{u}</loc><lastmod>{today}</lastmod></url>" for u in urls)
          + "</urlset>")
    (root / "sitemap.xml").write_text(sm, encoding="utf-8")
    print(f"  ok  sito v2: index.html + {len(cities)} pagine citta' + sitemap.xml + Metricool pixel")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("uso: generate_social_assets.py <assets/social/ma-NN-citta | --site>")
    if sys.argv[1] == "--site":
        build_site(Path(".").resolve())
    else:
        main(sys.argv[1])
