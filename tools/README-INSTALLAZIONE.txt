MERIDIAN ATLAS — GENERATORE ASSET SOCIAL
=========================================
Contenuto da copiare NELLA ROOT del repo GitHub Pages (meridianatlas.co):

  tools/generate_social_assets.py      -> motore
  .github/workflows/social-assets.yml  -> automazione GitHub
  assets/social/_fonts/                -> font brand (Playfair Bold + Inter)

Per ogni citta' creare SOLO:
  assets/social/ma-NN-citta/src/artwork.jpg   (mappa, orizzontale 3:2, >=3000px lato lungo)
  assets/social/ma-NN-citta/src/mockup.jpg    (Gemini 1000x1500)
  assets/social/ma-NN-citta/src/meta.json     (vedi esempio ma-01-milano)
  assets/social/ma-NN-citta/src/reel.mp4      (OPZIONALE, da Higgsfield)

Al push, GitHub genera da solo nella cartella citta':
  feed-a/b/c/d.jpg, story-1/2.jpg, pin-hero.jpg, pin-mockup.jpg, reel.mp4

Test locale (facoltativo):
  pip install pillow
  python tools/generate_social_assets.py assets/social/ma-01-milano
