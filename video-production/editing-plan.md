# Editing & Motion Plan (v2)

## Pacing

- 30 s on a 120 BPM grid; every event lands on a beat or an 8th note.
- **Fast:** 0–8 s (a new element every 0.25–0.5 s).
- **Breathing moments:** the 0.25 s frozen gap (7.75–8.00), and the end card (26.0–30.0, 4 s).
- The feature sections each hold one panel for about 4 s while details animate inside it: fast in feel, readable in content.
- There are no hard cuts in the main film. It is one continuous motion-design move linked by the sweep (8.00) and three whip pans (14.00, 18.00, 22.00). The cutdowns use hard cuts on beats.

## Transitions (the only ones used)

| Time | Transition | Motivation |
|---|---|---|
| 8.00–8.35 | Mint sweep wipe (right → left) with a light trail; the noise blows outward | The product clears the noise |
| 13.85–14.35 · 17.85–18.35 · 21.85–22.35 | Whip pan: the outgoing panel exits right with blur, the next enters from the left | Moving forward (RTL) through the product |
| 25.00–25.70 | Panels fly into a 2×2 composition | "The full picture" |
| 25.90–26.60 | Panels dim to 30% and blur | Hand-off to the end card |

## Motion rules

See `visual-continuity-bible.md` §4. There's one text animation (the mask reveal), expo-out arrivals, a kick pulse of +0.8%, number easing over 1.2 s, and 6-sample motion blur.

## Color and texture

A deep-green world is graded in the source: no LUT, sRGB/Rec.709 output, 6% overlay grain. Mint `#41D7B2` stays exact; don't push saturation.

## End card

| Element | 16:9 | 9:16 |
|---|---|---|
| Headline "העסק מכר. / אתם כבר בתמונה." | Center, top 300 → 240 px, 120 px | Center, top 640 → 570 px, 120 px |
| Lockup | y 610 | y 1000 |
| CTA "פתיחת חשבון ←" | y 750 | y 1170 |
| URL | y 860 (the 6 s cut omits it) | y 1290 |

End-card duration: 4.0 s (26.0–30.0); the CTA is readable from 27.5 s.

## Safe margins

- 16:9: all text inside 10% title-safe.
- 9:16: text kept in y 270–1250 px (top 14% and bottom 35% free for the Reels UI), 6% sides.

## Captions

No speech, so no dialogue subtitles. A Hebrew SDH sidecar describes the sound: `exports/main/sydney-30s-16x9.he.srt`.

## Export

H.264 High, yuv420p, CRF 17, `+faststart`, BT.709 tags; AAC 320 kbps 48 kHz; −14 LUFS. 16:9 = 1920×1080, 9:16 = 1080×1920, 24 fps. Rebuild everything with `tools/build.sh`.
