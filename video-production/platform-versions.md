# Platform Versions (v2)

All versions share one source (`tools/film.html`) and one mix (`tools/score.py`). Cutdowns are built by remapping output time to source time, so every picture segment and its audio come from identical source times.

## 1. Main 16:9 — 30.0 s · `exports/main/sydney-30s-16x9.mp4`
Website hero / landing page, YouTube, LinkedIn. The timeline is in `script-and-timeline.md`.

## 2. Main 9:16 — 30.0 s · `exports/vertical/sydney-30s-9x16.mp4`
Reels / Stories. Same timeline and audio. The layout is recomposed rather than cropped:
- Headlines at the top (right 70 px, top 300 px, 96 px) and the product panel below (x 50–1030, from y 740).
- Hero/question type 150/118 px, centered around y 800–830.
- The "doc status" badge is hidden in list rows to keep them readable at phone width.
- Finale slots stacked in a vertical 2×2.
- Safe zones: nothing important above y 270 or below y 1250.

## 3. 1:1 — specified, not rendered
Derive it from the 9:16 layout with the panel scaled to 86% width and headlines at 72 px. Same timing.

## 4. 15 s cutdown · `exports/cutdowns/sydney-15s-{16x9,9x16}.mp4`

| Output | Source | Content |
|---|---|---|
| 0.0–2.0 | 0.0–2.0 | Sales slam in with beeps |
| 2.0–4.0 | 6.0–8.0 | "כמה באמת נכנס?" + the frozen gap |
| 4.0–6.0 | 8.0–10.0 | The drop: sweep, "מנהל הכנסות לעסקים", lockup |
| 6.0–8.0 | 11.0–13.0 | Sales land automatically (headline already on screen) |
| 8.0–10.5 | 14.0–16.5 | The net figure updates with its breakdown |
| 10.5–15.0 | 25.5–30.0 | Panels → end card, CTA, URL, sonic logo |

Kept: the hook, the problem, the drop, two features, the end card. Removed: the attention list and the assistant. End card: 4.5 s.

## 5. 6 s hook · `exports/cutdowns/sydney-06s-{16x9,9x16}.mp4`

| Output | Source | Content |
|---|---|---|
| 0.0–2.0 | 0.0–2.0 | Sales slam in with beeps |
| 2.0–3.0 | 8.0–9.0 | The mint sweep + amounts snapping into the list |
| 3.0–6.0 | 27.0–30.0 | End card with lockup + CTA (the URL is omitted; the ad link carries it) + sonic logo |
