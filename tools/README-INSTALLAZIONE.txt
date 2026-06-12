MERIDIAN ATLAS — GENERATORE ASSET SOCIAL v2 (mockup-first)
===========================================================
PRINCIPIO: i tuoi mockup sono asset finiti. Lo script non li tocca nel
contenuto: li riadatta solo ai formati piattaforma (pin / feed 4:5 / story 9:16).

Da copiare NELLA ROOT del repo GitHub Pages (meridianatlas.co):
  tools/generate_social_assets.py
  .github/workflows/social-assets.yml
  assets/social/_fonts/

Per ogni citta' creare SOLO:
  assets/social/ma-NN-citta/src/artwork.jpg        mappa 3:2, >=3000px lato lungo
  assets/social/ma-NN-citta/src/mockups/*.jpg      i TUOI mockup finiti (N qualsiasi)
  assets/social/ma-NN-citta/src/meta.json          dati + opzioni (vedi esempio)
  assets/social/ma-NN-citta/src/reel.mp4           opzionale (Higgsfield)

Output automatici al push:
  per ogni mockup:  <nome>-pin.jpg, <nome>-feed.jpg, <nome>-story.jpg
  dall'artwork:     feed-artwork, feed-detail, feed-card, story-artwork,
                    pin-typo (variante anti-duplicato), reel.mp4

Opzioni in meta.json:
  feed_crop:    top|center|bottom  (default top: protegge il testo nei 220px alti)
  story_mode:   bands|fill         (default bands)
  overlay_pins: true|false         (default false: i tuoi pin restano intatti)

Test locale (facoltativo):
  pip install pillow
  python tools/generate_social_assets.py assets/social/ma-01-milano
