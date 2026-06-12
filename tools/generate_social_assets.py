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
    reel(art_p, src, folder)
    build_site(folder.resolve().parents[2])


# ====================================================================== SITE =
SITE = "https://meridianatlas.co"
METRICOOL_PIXEL = '<img src="https://tracker.metricool.com/c3po.jpg?hash=44bdd722cca4b0fe96908e87b58222a9"/>'

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


CSS = """
:root{
  --ivory:#F2EDE2;--paper:#FBF7EF;--ink:#1A1A1A;--muted:#8A8378;
  --line:rgba(26,26,26,.22);--soft:rgba(26,26,26,.06);--accent:#53675E;
  --shadow:0 22px 60px rgba(26,26,26,.11);--max:1180px;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--ivory);color:var(--ink);font-family:Inter,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;line-height:1.55}
img,video{max-width:100%;display:block}
a{color:inherit;text-decoration:none}.wrap{max-width:var(--max);margin:0 auto;padding:0 clamp(20px,4vw,54px)}
.skip{position:absolute;left:-999px;top:10px;background:var(--ink);color:var(--ivory);padding:10px 14px;z-index:9}.skip:focus{left:10px}
.site-header{position:sticky;top:0;z-index:5;background:rgba(242,237,226,.88);backdrop-filter:blur(16px);border-bottom:1px solid var(--line)}
.nav{height:74px;display:flex;align-items:center;justify-content:space-between;gap:24px}.brand{font-size:12px;font-weight:700;letter-spacing:.34em;text-transform:uppercase}.nav-links{display:flex;align-items:center;gap:22px;flex-wrap:wrap}.nav-links a{font-size:11px;font-weight:700;letter-spacing:.24em;text-transform:uppercase;color:var(--muted)}.nav-links a:hover{color:var(--ink)}
.hero{padding:clamp(58px,9vw,118px) 0 clamp(42px,7vw,88px)}.hero-grid{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(300px,.95fr);gap:clamp(32px,6vw,78px);align-items:center}.eyebrow{font-size:12px;font-weight:800;letter-spacing:.34em;text-transform:uppercase;color:var(--muted)}
h1.display{font-family:'Playfair Display',Georgia,serif;font-weight:700;font-size:clamp(52px,8.2vw,108px);letter-spacing:.035em;line-height:.98;margin-top:18px}.lead{font-size:clamp(17px,2vw,22px);line-height:1.72;color:#45413A;margin-top:24px;max-width:720px}.hero-actions{display:flex;gap:14px;flex-wrap:wrap;margin-top:34px}.btn{display:inline-flex;align-items:center;justify-content:center;min-height:50px;padding:15px 24px;border:1.5px solid var(--ink);font-size:11px;font-weight:800;letter-spacing:.24em;text-transform:uppercase;transition:.2s ease}.btn.primary{background:var(--ink);color:var(--ivory)}.btn:hover{transform:translateY(-1px);box-shadow:0 10px 26px rgba(26,26,26,.12)}.btn.primary:hover{background:transparent;color:var(--ink)}.btn.muted{border-color:var(--line);color:var(--muted)}
.hero-card{position:relative}.hero-card:before{content:"";position:absolute;inset:24px -18px -18px 24px;border:1px solid var(--line);z-index:-1}.hero-card img{border:1.5px solid var(--ink);box-shadow:var(--shadow);background:var(--paper)}.stats{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin-top:48px}.stat{padding:20px 18px;text-align:center;border-left:1px solid var(--line)}.stat:first-child{border-left:0}.stat strong{font-family:'Playfair Display',Georgia,serif;font-size:30px}.stat span{display:block;font-size:10px;font-weight:800;letter-spacing:.28em;text-transform:uppercase;color:var(--muted);margin-top:4px}
.section{padding:clamp(58px,8vw,98px) 0;border-top:1px solid var(--line)}.section-head{display:flex;justify-content:space-between;align-items:end;gap:30px;margin-bottom:34px}.section-head h2{font-family:'Playfair Display',Georgia,serif;font-size:clamp(34px,5vw,58px);line-height:1.05;letter-spacing:.04em}.section-head p{max-width:440px;color:#534F48}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:42px 30px}.card{group:card}.plate{width:100%;border:1.5px solid var(--ink);background:var(--paper);transition:.25s ease}.card:hover .plate{transform:translateY(-4px);box-shadow:var(--shadow)}.card figcaption{margin-top:16px;text-align:center}.no{font-size:11px;font-weight:800;letter-spacing:.28em;color:var(--muted);text-transform:uppercase}.name{font-family:'Playfair Display',Georgia,serif;font-weight:700;font-size:23px;letter-spacing:.06em;margin-top:4px}.coords{font-size:12px;letter-spacing:.12em;color:var(--muted);margin-top:6px}.feature-row{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.feature{background:rgba(251,247,239,.55);border:1px solid var(--line);padding:28px}.feature h3{font-family:'Playfair Display',Georgia,serif;font-size:28px;margin-bottom:10px}.feature p{color:#534F48}.quote{font-family:'Playfair Display',Georgia,serif;font-size:clamp(30px,4.6vw,54px);line-height:1.14;text-align:center;max-width:920px;margin:auto}.quote small{display:block;font-family:Inter,Helvetica,Arial,sans-serif;font-size:11px;font-weight:800;letter-spacing:.28em;text-transform:uppercase;color:var(--muted);margin-top:24px}
.breadcrumb{font-size:11px;font-weight:800;letter-spacing:.22em;text-transform:uppercase;color:var(--muted);margin-bottom:24px}.city-hero{padding:clamp(42px,7vw,78px) 0}.city-title{display:grid;grid-template-columns:1fr minmax(300px,520px);gap:clamp(32px,6vw,72px);align-items:center}.city-title h1{font-family:'Playfair Display',Georgia,serif;font-size:clamp(56px,9vw,116px);line-height:.95;letter-spacing:.035em}.meta-line{display:flex;gap:18px;flex-wrap:wrap;margin-top:22px;color:var(--muted);font-size:12px;font-weight:800;letter-spacing:.2em;text-transform:uppercase}.story{font-size:18px;line-height:1.78;color:#45413A;margin-top:26px;max-width:680px}.city-panel{border:1px solid var(--line);background:rgba(251,247,239,.55);padding:24px;margin-top:30px}.city-panel dl{display:grid;grid-template-columns:120px 1fr;gap:10px 18px}.city-panel dt{font-size:11px;font-weight:800;letter-spacing:.22em;text-transform:uppercase;color:var(--muted)}.city-panel dd{font-size:14px}.gallery{display:grid;grid-template-columns:1.1fr .9fr;gap:28px;align-items:start}.gallery-stack{display:grid;gap:28px}.duo{display:grid;grid-template-columns:1fr 1fr;gap:28px}.caption{font-size:11px;font-weight:800;letter-spacing:.22em;text-transform:uppercase;color:var(--muted);margin-top:12px;text-align:center}.note{font-size:13px;color:var(--muted);margin-top:14px}.footer{border-top:1px solid var(--line);padding:34px 0 58px;text-align:center}.footer p{font-size:12px;letter-spacing:.1em;color:var(--muted)}:focus-visible{outline:2px solid var(--ink);outline-offset:4px}
@media(max-width:880px){.hero-grid,.city-title,.gallery{grid-template-columns:1fr}.feature-row,.duo{grid-template-columns:1fr}.section-head{display:block}.section-head p{margin-top:14px}.nav{height:auto;padding:20px 0;align-items:flex-start}.nav-links{justify-content:flex-end}.stats{grid-template-columns:1fr}.stat{border-left:0;border-top:1px solid var(--line)}.stat:first-child{border-top:0}.city-title .plate{max-width:520px;margin:auto}}
@media(max-width:560px){.brand{letter-spacing:.22em}.nav-links a{letter-spacing:.16em}.hero-actions{display:grid}.btn{width:100%}.city-panel dl{grid-template-columns:1fr}.grid{grid-template-columns:1fr 1fr;gap:28px 18px}.name{font-size:20px}}
""".strip() + "\n"


RM_JS = ('<script>if(matchMedia("(prefers-reduced-motion: reduce)").matches)'
         'document.querySelectorAll("video[autoplay]").forEach(v=>{v.removeAttribute("autoplay");v.pause()})'
         '</script>')


def _head(title, desc, og_image, canonical, css_href, extra_schema=None):
    title_e = _e(title)
    desc_e = _e(desc)
    canonical_e = _e(canonical)
    og_e = _e(_abs(og_image))
    schema = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Meridian Atlas Co.",
        "url": SITE,
        "description": "Editorial, AI-created city map prints for considered interiors."
    }
    if extra_schema:
        schema = [schema, extra_schema]
    schema_json = json.dumps(schema, ensure_ascii=False)
    return (f'<!doctype html>\n<html lang="en">\n<head>\n'
            f'  <meta charset="utf-8">\n'
            f'  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'  <title>{title_e}</title>\n'
            f'  <meta name="description" content="{desc_e}">\n'
            f'  <link rel="canonical" href="{canonical_e}">\n'
            f'  <meta property="og:type" content="website">\n'
            f'  <meta property="og:title" content="{title_e}">\n'
            f'  <meta property="og:description" content="{desc_e}">\n'
            f'  <meta property="og:image" content="{og_e}">\n'
            f'  <meta property="og:url" content="{canonical_e}">\n'
            f'  <meta name="twitter:card" content="summary_large_image">\n'
            f'  <link rel="stylesheet" href="{_e(css_href)}">\n'
            f'  <script type="application/ld+json">{schema_json}</script>\n'
            f'</head>\n')


def _header(home_link="/", label="Atlas"):
    return (f'<a class="skip" href="#content">Skip to content</a>'
            f'<header class="site-header"><div class="wrap nav">'
            f'<a class="brand" href="{_e(home_link)}">Meridian Atlas Co.</a>'
            f'<nav class="nav-links" aria-label="Main navigation">'
            f'<a href="/">{_e(label)}</a><a href="/#atlas">Cities</a><a href="/#process">Process</a>'
            f'</nav></div></header>')


FOOTER = ('<footer class="footer"><div class="wrap">'
          '<p>All artworks are AI-created and refined for archival printing.</p>'
          '<p>© Meridian Atlas Co. - Editorial wall art for the cities you love.</p>'
          '</div></footer>')


def _page_end():
    # Metricool tracking pixel: appended by every generated HTML page.
    return FOOTER + METRICOOL_PIXEL + RM_JS + '</body></html>'


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


def _city_page(m):
    slug, nn, city = m["_slug"], str(m["nn"]), m["city"]
    country = m.get("country", "")
    coords = m.get("coords", "")
    desc = m.get("story") or (f"{city} - City Atlas No. {nn}. Editorial, AI-created map print in sage, dusty blue and warm ivory.")
    canonical = f"{SITE}/{slug}/"
    artwork = _asset(slug, "feed-artwork.jpg")
    detail = _asset(slug, "feed-detail.jpg")
    card = _asset(slug, "feed-card.jpg")
    reel = _asset(slug, "reel.mp4")
    mockup = _asset(slug, m["_mockup_feed"]) if m.get("_mockup_feed") else ""
    product_schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": f"{city} City Atlas Print",
        "brand": {"@type": "Brand", "name": "Meridian Atlas Co."},
        "image": _abs(artwork),
        "description": desc,
        "url": canonical
    }
    gallery_mockup = (f'<figure><img class="plate" src="{_e(mockup)}" alt="{_e(city)} framed map print mockup" loading="lazy">'
                      f'<figcaption class="caption">Interior scale</figcaption></figure>') if mockup else ""
    reel_html = (f'<figure><video class="plate" autoplay muted loop playsinline preload="metadata" src="{_e(reel)}"></video>'
                 f'<figcaption class="caption">Motion preview</figcaption></figure>') if m.get("_has_reel") else ""
    return (
        _head(f"{city} City Atlas Print - No. {nn} | Meridian Atlas Co.", desc, artwork, canonical, "../style.css", product_schema)
        + '<body>' + _header("/", "Home")
        + '<main id="content" class="wrap">'
        + '<section class="city-hero"><p class="breadcrumb"><a href="/">The Atlas</a> / City print</p>'
        + '<div class="city-title"><div>'
        + f'<p class="eyebrow">City Atlas - No. {_e(nn)}</p><h1>{_e(city)}</h1>'
        + f'<div class="meta-line"><span>{_e(country)}</span><span>{_e(coords)}</span></div>'
        + f'<p class="story">{_e(desc)}</p>'
        + '<div class="hero-actions">' + _cta_html(m) + '<a class="btn" href="/#atlas">Explore the series</a></div>'
        + '<div class="city-panel"><dl>'
        + f'<dt>Series</dt><dd>City Atlas - No. {_e(nn)}</dd>'
        + f'<dt>Palette</dt><dd>Sage, dusty blue and warm ivory</dd>'
        + f'<dt>Method</dt><dd>AI-created artwork, editorial layout, print-ready assets</dd>'
        + '</dl><p class="note">Availability and final print options are managed on Redbubble.</p></div>'
        + '</div>'
        + f'<figure><img class="plate" src="{_e(artwork)}" alt="{_e(city)} editorial city map print"></figure>'
        + '</div></section>'
        + '<section class="section"><div class="section-head"><div><p class="eyebrow">Gallery</p><h2>Artwork, details and campaign assets.</h2></div><p>Each city page now presents the print as a small product story instead of a basic image gallery.</p></div>'
        + '<div class="gallery"><div class="gallery-stack">'
        + f'<figure><img class="plate" src="{_e(detail)}" alt="{_e(city)} map detail" loading="lazy"><figcaption class="caption">Map detail</figcaption></figure>'
        + gallery_mockup + '</div><div class="gallery-stack">'
        + f'<figure><img class="plate" src="{_e(card)}" alt="{_e(city)} typographic coordinates card" loading="lazy"><figcaption class="caption">Coordinates card</figcaption></figure>'
        + reel_html + '</div></div></section>'
        + '</main>' + _page_end())


def _index_page(cities):
    count = len(cities)
    first = cities[0] if cities else None
    latest = cities[-1] if cities else None
    og = _asset(first["_slug"], "feed-artwork.jpg") if first else "/"
    cards = "".join(
        f'<a class="card" href="/{_e(m["_slug"])}/"><figure>'
        f'<img class="plate" src="{_e(_asset(m["_slug"], "pin-typo.jpg"))}" '
        f'alt="{_e(m["city"])} map print - City Atlas No. {_e(m["nn"])}" loading="lazy">'
        f'<figcaption><div class="no">No. {_e(m["nn"])}</div><div class="name">{_e(m["city"])}</div>'
        f'<div class="coords">{_e(m.get("coords", ""))}</div></figcaption></figure></a>'
        for m in cities)
    featured = ""
    if first:
        featured = (f'<div class="hero-card"><img src="{_e(_asset(first["_slug"], "feed-artwork.jpg"))}" '
                    f'alt="Featured Meridian Atlas city print: {_e(first["city"])}"></div>')
    latest_name = latest.get("city") if latest else "New cities"
    return (
        _head("The City Atlas - Meridian Atlas Co.",
              "A numbered series of editorial, AI-created city map prints - sage, dusty blue and warm ivory, designed for considered interiors.",
              og, f"{SITE}/", "style.css")
        + '<body>' + _header("/", "Atlas")
        + '<main id="content">'
        + '<section class="wrap hero"><div class="hero-grid"><div>'
        + '<p class="eyebrow">Meridian Atlas Co.</p><h1 class="display">The City Atlas</h1>'
        + '<p class="lead">Editorial map prints for the cities you love: a numbered collection with refined typography, calm palettes and campaign-ready visual assets.</p>'
        + '<div class="hero-actions"><a class="btn primary" href="#atlas">Explore the atlas</a><a class="btn" href="#process">How it is made</a></div>'
        + f'<div class="stats"><div class="stat"><strong>{count}</strong><span>Published cities</span></div><div class="stat"><strong>AI</strong><span>Created artwork</span></div><div class="stat"><strong>{_e(latest_name)}</strong><span>Latest plate</span></div></div>'
        + '</div>' + featured + '</div></section>'
        + '<section id="atlas" class="wrap section"><div class="section-head"><div><p class="eyebrow">The numbered series</p><h2>Choose a city. Keep the memory.</h2></div><p>Each plate combines map texture, coordinates and editorial restraint, prepared for premium wall-art presentation.</p></div>'
        + f'<div class="grid">{cards}</div></section>'
        + '<section id="process" class="wrap section"><div class="section-head"><div><p class="eyebrow">Process</p><h2>From city data to collectible print.</h2></div><p>The site generator now presents the collection with richer storytelling, stronger calls to action and cleaner product pages.</p></div>'
        + '<div class="feature-row"><article class="feature"><h3>01 - Atlas</h3><p>Every city receives a numbered identity with coordinates, country and a consistent editorial system.</p></article><article class="feature"><h3>02 - Artwork</h3><p>AI-created map compositions are refined into feed, story, pin, detail and motion assets.</p></article><article class="feature"><h3>03 - Print</h3><p>City pages guide visitors from discovery to the Redbubble print page with trackable campaign links.</p></article></div></section>'
        + '<section class="wrap section"><p class="quote">“A calm atlas for modern interiors - city memories translated into quiet, architectural wall art.”<small>Meridian Atlas Co.</small></p></section>'
        + '</main>' + _page_end())


def build_site(root: Path):
    cities = _live_cities(root)
    if not cities:
        print("  --  sito: nessuna citta' pubblicata, salto")
        return

    # Il sito viene pubblicato direttamente nella root del repository,
    # quindi su https://meridianatlas.co/.
    (root / "style.css").write_text(CSS, encoding="utf-8")
    (root / "index.html").write_text(_index_page(cities), encoding="utf-8")

    urls = [f"{SITE}/"]
    for m in cities:
        d = root / m["_slug"]
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(_city_page(m), encoding="utf-8")
        urls.append(f"{SITE}/{m['_slug']}/")

    from datetime import date as _date
    today = _date.today().isoformat()
    sm = ('<?xml version="1.0" encoding="UTF-8"?>'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{u}</loc><lastmod>{today}</lastmod></url>" for u in urls)
          + "</urlset>")
    (root / "sitemap.xml").write_text(sm, encoding="utf-8")
    print(f"  ok  sito: index.html + {len(cities)} pagine citta' in root + sitemap.xml + Metricool pixel")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("uso: generate_social_assets.py <assets/social/ma-NN-citta | --site>")
    if sys.argv[1] == "--site":
        build_site(Path(".").resolve())
    else:
        main(sys.argv[1])
