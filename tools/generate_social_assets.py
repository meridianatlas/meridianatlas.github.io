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
  --ivory:#F2EDE2;--paper:#FBF7EF;--ink:#191917;--muted:#81796D;--line:rgba(25,25,23,.20);
  --sage:#617468;--blue:#9AA9B0;--max:1160px;--pad:clamp(20px,4vw,52px);
}
*{box-sizing:border-box}html,body{margin:0;padding:0;max-width:100%;overflow-x:hidden}html{scroll-behavior:smooth}
body{background:var(--ivory);color:var(--ink);font-family:Inter,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;line-height:1.55}
img,video{display:block;max-width:100%;height:auto}a{color:inherit;text-decoration:none}.wrap{width:min(var(--max),100%);margin-inline:auto;padding-inline:var(--pad)}
.skip{position:absolute;left:-999px;top:10px;background:var(--ink);color:var(--ivory);padding:10px 14px;z-index:20}.skip:focus{left:10px}.site-header{position:sticky;top:0;z-index:10;background:rgba(242,237,226,.92);backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}
.nav{min-height:76px;display:flex;align-items:center;justify-content:space-between;gap:22px}.brand{font-size:12px;font-weight:800;letter-spacing:.34em;text-transform:uppercase;white-space:nowrap}.nav-links{display:flex;gap:22px;align-items:center;flex-wrap:wrap}.nav-links a{font-size:11px;font-weight:800;letter-spacing:.22em;text-transform:uppercase;color:var(--muted)}.nav-links a:hover{color:var(--ink)}
.eyebrow{font-size:11px;font-weight:850;letter-spacing:.30em;text-transform:uppercase;color:var(--muted)}.btn{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:14px 22px;border:1.4px solid var(--ink);font-size:11px;font-weight:850;letter-spacing:.20em;text-transform:uppercase;transition:.18s ease;background:transparent}.btn.primary{background:var(--ink);color:var(--ivory)}.btn:hover{transform:translateY(-1px)}.btn.primary:hover{background:transparent;color:var(--ink)}.btn.muted{border-color:var(--line);color:var(--muted)}
.home-hero{padding:clamp(46px,8vw,92px) 0 clamp(46px,7vw,82px)}.home-hero-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(280px,430px);gap:clamp(30px,6vw,74px);align-items:center}.kicker-line{display:flex;align-items:center;gap:14px}.kicker-line:after{content:"";height:1px;background:var(--line);flex:1;max-width:180px}.home-title{font-family:'Playfair Display',Georgia,serif;font-weight:700;font-size:clamp(52px,9vw,104px);line-height:.92;letter-spacing:.025em;margin:18px 0 0;max-width:720px}.home-title em{font-style:italic;font-weight:700}.lead{font-size:clamp(17px,2vw,21px);line-height:1.65;color:#444039;margin:24px 0 0;max-width:650px}.hero-actions{display:flex;gap:14px;flex-wrap:wrap;margin-top:30px}.hero-note{margin-top:28px;padding-left:18px;border-left:2px solid var(--sage);color:var(--muted);font-size:14px;max-width:560px}.hero-art{position:relative;padding:16px;border:1px solid var(--line);background:rgba(251,247,239,.55)}.hero-art:before{content:"";position:absolute;inset:10px;border:1px solid var(--ink);pointer-events:none}.hero-art img{aspect-ratio:4/5;width:100%;object-fit:cover;border:1px solid var(--ink);background:var(--paper)}.hero-art figcaption{display:flex;justify-content:space-between;gap:12px;margin-top:14px;font-size:10px;font-weight:850;letter-spacing:.22em;text-transform:uppercase;color:var(--muted)}
.marquee{border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:14px 0;overflow:hidden}.marquee-inner{display:flex;gap:28px;white-space:nowrap;font-size:11px;font-weight:850;letter-spacing:.28em;text-transform:uppercase;color:var(--muted);animation:drift 28s linear infinite}@keyframes drift{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.section{padding:clamp(54px,8vw,92px) 0;border-top:1px solid var(--line)}.section-head{display:grid;grid-template-columns:minmax(0,1fr) minmax(260px,420px);gap:30px;align-items:end;margin-bottom:34px}.section-head h2{font-family:'Playfair Display',Georgia,serif;font-size:clamp(34px,5vw,58px);line-height:1.03;letter-spacing:.035em;margin:10px 0 0}.section-head p{color:#514C44;margin:0}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:38px 28px}.card .plate{width:100%;aspect-ratio:2/3;object-fit:cover;border:1.4px solid var(--ink);background:var(--paper);transition:.22s ease}.card:hover .plate{transform:translateY(-4px);box-shadow:0 18px 44px rgba(25,25,23,.13)}.card figcaption{text-align:center;margin-top:14px}.no{font-size:10px;font-weight:850;letter-spacing:.28em;color:var(--muted);text-transform:uppercase}.name{font-family:'Playfair Display',Georgia,serif;font-size:22px;font-weight:700;letter-spacing:.05em;margin-top:4px}.coords{font-size:11px;letter-spacing:.12em;color:var(--muted);margin-top:5px}.feature-row{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.feature{border:1px solid var(--line);background:rgba(251,247,239,.48);padding:26px}.feature h3{font-family:'Playfair Display',Georgia,serif;font-size:27px;line-height:1.1;margin:0 0 10px}.feature p{margin:0;color:#514C44}.quote{font-family:'Playfair Display',Georgia,serif;font-size:clamp(30px,4.6vw,54px);line-height:1.14;text-align:center;max-width:900px;margin:0 auto}.quote small{display:block;font-family:Inter,Helvetica,Arial,sans-serif;font-size:11px;font-weight:850;letter-spacing:.25em;text-transform:uppercase;color:var(--muted);margin-top:24px}
.breadcrumb{font-size:11px;font-weight:850;letter-spacing:.20em;text-transform:uppercase;color:var(--muted);margin:0 0 24px}.city-hero{padding:clamp(42px,7vw,78px) 0}.city-title{display:grid;grid-template-columns:minmax(0,1fr) minmax(280px,520px);gap:clamp(30px,6vw,70px);align-items:center}.city-title h1{font-family:'Playfair Display',Georgia,serif;font-size:clamp(52px,9vw,112px);line-height:.95;letter-spacing:.025em;margin:16px 0 0}.meta-line{display:flex;gap:16px;flex-wrap:wrap;margin-top:22px;color:var(--muted);font-size:12px;font-weight:850;letter-spacing:.18em;text-transform:uppercase}.story{font-size:18px;line-height:1.75;color:#444039;margin:26px 0 0;max-width:680px}.city-panel{border:1px solid var(--line);background:rgba(251,247,239,.5);padding:24px;margin-top:30px}.city-panel dl{display:grid;grid-template-columns:118px 1fr;gap:10px 18px;margin:0}.city-panel dt{font-size:11px;font-weight:850;letter-spacing:.20em;text-transform:uppercase;color:var(--muted)}.city-panel dd{font-size:14px;margin:0}.plate{border:1.4px solid var(--ink);background:var(--paper)}.gallery{display:grid;grid-template-columns:1.08fr .92fr;gap:28px;align-items:start}.gallery-stack{display:grid;gap:28px}.caption{font-size:11px;font-weight:850;letter-spacing:.20em;text-transform:uppercase;color:var(--muted);margin-top:12px;text-align:center}.note{font-size:13px;color:var(--muted);margin:14px 0 0}.footer{border-top:1px solid var(--line);padding:34px 0 58px;text-align:center}.footer p{font-size:12px;letter-spacing:.1em;color:var(--muted);margin:4px 0}:focus-visible{outline:2px solid var(--ink);outline-offset:4px}
@media(max-width:900px){.home-hero-grid,.city-title,.gallery,.section-head{grid-template-columns:1fr}.hero-art{max-width:420px;margin-inline:auto}.feature-row{grid-template-columns:1fr}.nav{align-items:flex-start;padding:20px 0}.nav-links{justify-content:flex-end}.marquee-inner{animation:none;flex-wrap:wrap;white-space:normal}.city-title .plate{max-width:520px;margin:auto}}
@media(max-width:560px){.brand{letter-spacing:.20em;font-size:11px}.nav-links{gap:14px}.nav-links a{letter-spacing:.14em}.hero-actions{display:grid}.btn{width:100%}.grid{grid-template-columns:1fr 1fr;gap:28px 18px}.home-title{font-size:clamp(48px,16vw,72px)}.lead{font-size:16px}.city-panel dl{grid-template-columns:1fr}.hero-art{padding:12px}.hero-art figcaption{display:block}.home-hero{padding-top:38px}}
@media(prefers-reduced-motion:reduce){.marquee-inner{animation:none}html{scroll-behavior:auto}.btn,.plate{transition:none}}
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
          '<p>© Meridian Atlas Co. — Editorial wall art for the cities you love.</p>'
          '</div></footer>')


def _page_end():
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
    desc = m.get("story") or (f"{city} — City Atlas No. {nn}. Editorial, AI-created map print in sage, dusty blue and warm ivory.")
    canonical = f"{SITE}/{slug}/"
    artwork = _asset(slug, "feed-artwork.jpg")
    detail = _asset(slug, "feed-detail.jpg")
    card = _asset(slug, "feed-card.jpg")
    reel = _asset(slug, "reel.mp4")
    mockup = _asset(slug, m["_mockup_feed"]) if m.get("_mockup_feed") else ""
    product_schema = {"@context":"https://schema.org","@type":"Product","name":f"{city} City Atlas Print","brand":{"@type":"Brand","name":"Meridian Atlas Co."},"image":_abs(artwork),"description":desc,"url":canonical}
    gallery_mockup = (f'<figure><img class="plate" src="{_e(mockup)}" alt="{_e(city)} framed map print mockup" loading="lazy"><figcaption class="caption">Interior scale</figcaption></figure>') if mockup else ""
    reel_html = (f'<figure><video class="plate" autoplay muted loop playsinline preload="metadata" src="{_e(reel)}"></video><figcaption class="caption">Motion preview</figcaption></figure>') if m.get("_has_reel") else ""
    return (_head(f"{city} City Atlas Print — No. {nn} | Meridian Atlas Co.", desc, artwork, canonical, "../style.css", product_schema)
        + '<body>' + _header("/", "Home")
        + '<main id="content" class="wrap"><section class="city-hero"><p class="breadcrumb"><a href="/">The Atlas</a> / City print</p><div class="city-title"><div>'
        + f'<p class="eyebrow">City Atlas — No. {_e(nn)}</p><h1>{_e(city)}</h1><div class="meta-line"><span>{_e(country)}</span><span>{_e(coords)}</span></div><p class="story">{_e(desc)}</p>'
        + '<div class="hero-actions">' + _cta_html(m) + '<a class="btn" href="/#atlas">Explore the series</a></div>'
        + '<div class="city-panel"><dl>'
        + f'<dt>Series</dt><dd>City Atlas — No. {_e(nn)}</dd><dt>Palette</dt><dd>Sage, dusty blue and warm ivory</dd><dt>Method</dt><dd>AI-created artwork, editorial layout, print-ready assets</dd>'
        + '</dl><p class="note">Availability and final print options are managed on Redbubble.</p></div></div>'
        + f'<figure><img class="plate" src="{_e(artwork)}" alt="{_e(city)} editorial city map print"></figure></div></section>'
        + '<section class="section"><div class="section-head"><div><p class="eyebrow">Gallery</p><h2>Artwork, details and campaign assets.</h2></div><p>Each city page presents the print as a small product story instead of a basic image gallery.</p></div>'
        + '<div class="gallery"><div class="gallery-stack">'
        + f'<figure><img class="plate" src="{_e(detail)}" alt="{_e(city)} map detail" loading="lazy"><figcaption class="caption">Map detail</figcaption></figure>'
        + gallery_mockup + '</div><div class="gallery-stack">'
        + f'<figure><img class="plate" src="{_e(card)}" alt="{_e(city)} typographic coordinates card" loading="lazy"><figcaption class="caption">Coordinates card</figcaption></figure>'
        + reel_html + '</div></div></section></main>' + _page_end())


def _index_page(cities):
    count = len(cities)
    first = cities[0] if cities else None
    latest = cities[-1] if cities else None
    og = _asset(first["_slug"], "feed-artwork.jpg") if first else "/"
    cards = "".join(
        f'<a class="card" href="/{_e(m["_slug"])}/"><figure><img class="plate" src="{_e(_asset(m["_slug"], "pin-typo.jpg"))}" alt="{_e(m["city"])} map print — City Atlas No. {_e(m["nn"])}" loading="lazy"><figcaption><div class="no">No. {_e(m["nn"])}</div><div class="name">{_e(m["city"])}</div><div class="coords">{_e(m.get("coords", ""))}</div></figcaption></figure></a>'
        for m in cities)
    featured = ""
    latest_name = latest.get("city") if latest else "New cities"
    if first:
        featured = (f'<figure class="hero-art"><img src="{_e(_asset(first["_slug"], "feed-artwork.jpg"))}" alt="Featured Meridian Atlas city print: {_e(first["city"])}"><figcaption><span>No. {_e(first["nn"])}</span><span>{_e(first["city"])}</span></figcaption></figure>')
    city_names = " • ".join(_e(m.get("city", "")) for m in cities[:12])
    marquee = (city_names + " • Editorial city prints • AI-created wall art • ") * 2
    return (_head("Meridian Atlas Co. — Editorial City Map Prints",
              "Premium editorial city map prints: a numbered collection of AI-created atlas artworks in sage, dusty blue and warm ivory.", og, f"{SITE}/", "style.css")
        + '<body>' + _header("/", "Atlas") + '<main id="content">'
        + '<section class="home-hero wrap"><div class="home-hero-grid"><div><div class="kicker-line"><p class="eyebrow">Numbered city prints</p></div>'
        + '<h1 class="home-title">Quiet maps for <em>places that stay.</em></h1>'
        + '<p class="lead">Meridian Atlas Co. turns city memories into restrained, architectural wall art: map textures, exact coordinates and a calm editorial palette designed for modern interiors.</p>'
        + '<div class="hero-actions"><a class="btn primary" href="#atlas">View the collection</a><a class="btn" href="#process">The process</a></div>'
        + f'<p class="hero-note">{count} published city plates. Latest release: {_e(latest_name)}. Each artwork is generated, refined and prepared as a collectible print story.</p>'
        + '</div>' + featured + '</div></section>'
        + f'<div class="marquee" aria-hidden="true"><div class="marquee-inner"><span>{marquee}</span><span>{marquee}</span></div></div>'
        + '<section id="atlas" class="wrap section"><div class="section-head"><div><p class="eyebrow">The atlas</p><h2>A collectible plate for every city.</h2></div><p>Browse the numbered series: each city has a dedicated page with artwork, details, preview assets and a direct print link where available.</p></div>'
        + f'<div class="grid">{cards}</div></section>'
        + '<section id="process" class="wrap section"><div class="section-head"><div><p class="eyebrow">Process</p><h2>Designed like a print collection, not a file dump.</h2></div><p>The generator builds a complete editorial system from the source artwork: homepage, city pages, gallery assets, motion previews, SEO metadata and tracking.</p></div>'
        + '<div class="feature-row"><article class="feature"><h3>01<br>City identity</h3><p>Each release receives a number, coordinates, country label and consistent typographic treatment.</p></article><article class="feature"><h3>02<br>Atlas artwork</h3><p>AI-created map compositions are refined into product, detail, pin, story and reel assets.</p></article><article class="feature"><h3>03<br>Print path</h3><p>Visitors move from discovery to the Redbubble print page through clear, trackable calls to action.</p></article></div></section>'
        + '<section class="wrap section"><p class="quote">“A calm atlas for modern interiors — city memories translated into quiet architectural wall art.”<small>Meridian Atlas Co.</small></p></section>'
        + '</main>' + _page_end())


def build_site(root: Path):
    cities = _live_cities(root)
    if not cities:
        print("  --  sito: nessuna citta' pubblicata, salto")
        return
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
