# Editing & Motion Plan

## Pacing

- **Overall:** musical by day, uneasy by night, precise in the product section, calm at the end. 17 shots in 45 s; **average shot length 2.65 s** (range 1.25–6.50 s).
- **Fast sections:** 00:00–00:03.75 (three payments in 3.75 s) and 00:20.00–00:24.75 (tap → sale lands).
- **Quiet sections:** 00:17.50–00:20.00 (black), 00:36.25–00:38.50 (lamp off, empty studio).
- **Moments that must breathe (never trim below):** S03 ≥ 3.5 s, S12 ≥ 4.0 s, S13 ≥ 2.5 s, S17 ≥ 6.0 s.

## Exact cut points (master)

`00:01.75 · 00:03.25 · 00:07.00 · 00:08.50 · 00:11.25 · 00:13.25 · 00:15.25 · 00:17.50 · 00:20.00 · 00:21.25 · 00:24.75 · 00:29.00 · 00:31.50 · 00:34.25 · 00:36.25 · 00:38.00–00:38.50 (dissolve)`

All cuts sit on 6-frame boundaries at 24 fps.

## Connective devices

| Type | Where | Notes |
|---|---|---|
| **Match cut (composition)** | S03→S04 (via S01's framing): S04 is S01's exact framing at night | The terminal is the pivot object |
| **Match cut (composition)** | S05 ≡ S13 ≡ S16 | Overlay-check them in the timeline at 50% opacity; they must align < 1% |
| **Match cut (framing)** | S07 ↔ S15 | Same face position and size; only the light, horizon and expression change |
| **Action cut** | S01 (card lifts) → S02; S06 (strike-through ends) → S07; S15 (lid closes) → S16 | Cut on the completion of the action |
| **J-cut** | Night hum enters 0.20 s before S04; Night-2 hum 0.25 s before S13 | Sound leads picture into night |
| **L-cut** | S03's door close carries 0.15 s into S04; S16's door close carries into S17 | Sound trails |
| **Sound bridge** | Beep 1 bridges S09 (black) → S10 → S11: the same beep causes the UI tick | Cause and effect through sound |
| **Hard cut to silence** | S08 → S09 at 00:17.50 | Picture and sound cut together, no fade |
| **Dissolve** | S16 → S17, 12 frames (00:38.00–00:38.50) | The window's cyan glow into the end card's mint wave; the only dissolve in the film |

## Speed changes

Only S01/S10: 48 fps source conformed to 24 fps (0.5×) — motivated by the macro. No speed ramps anywhere.

## Visual transitions

None other than the dissolve above. No wipes, zooms, glitches, light leaks or whip-pans.

## Text animation (one system)

- Enter: opacity 0→1, translateY 12 px→0, 400 ms, `cubic-bezier(0.25, 1, 0.5, 1)`.
- Exit: opacity 1→0, 300 ms, ease-in.
- Multi-line: lines stagger 120 ms.
- End-card headline: rises 40 px over 600 ms at 00:41.00 to make room for the lockup.
- Exact per-element timings: `on-screen-copy.md`.

## Motion-graphics style (S09, S11, S12, S14, S17)

- Backdrop: radial `#14463A` (top-right) → `#0B2A22` → `#071A15`; `sydney-hero-clean.png` at 16–22% opacity, blurred 6 px, drifting ≤ 1% per shot.
- Panels: product dark theme, 18 px radius, 1 px `rgba(255,255,255,0.09)` border, `rgba(8,36,31,0.72)` fill, a deep soft shadow; virtual camera push-in 2% per shot, linear.
- Rows enter from the right (24 px), 360 ms, ease-out-quart. Removed items exit to the left.
- Numbers ease between values over 1.2 s with ease-out-quart (the product's behaviour), tabular figures so digits never jitter.
- Highlights: a mint 14% fill + 1 px mint border, fade out over 1.2 s.
- Cursor: macOS-style arrow, white with a dark outline, moves on a gentle curve, 450 ms; the click shows a 6 px press (scale 0.94) — no ripple circles.
- **Rebuild UI from real capture:** capture מכירות, לוח בקרה and דורש טיפול in the running product (dark theme, a fictional demo workspace, 2× device-pixel ratio), then rebuild the needed parts in After Effects as vector layers using the same strings. The HTML rebuild in `tools/film.html` is the reference animation.

## Color-grading direction (DaVinci Resolve)

| Section | White balance | Contrast / curve | Saturation | Color notes |
|---|---|---|---|---|
| Day | 5400 K neutral-warm | Soft S-curve, blacks lifted to ≈ 3 IRE | 95% | Plaster stays off-white (not blue); the mint glow kept at `#41D7B2` |
| Night 1 | Mixed: face highlights pushed cold (hue ≈ 210°), mids desaturated toward grey-green | Harder curve, blacks at 0, highlight roll-off steep | 78–82% | The lamp's hot spot slightly clipped; a murky, uneasy feel |
| Night 2 | Warm key 2700 K preserved; shadows pushed toward `#0B2A22` teal | Medium curve, rich shadows with detail | 95% | Amber skin + teal shadows = brand harmony; clean blacks |
| MG / end card | — | — | — | Match the backdrop's black to the Night 2 shadows so the dissolve is seamless |

**Skin tones:** keep skin on the vectorscope's skin-tone indicator line in Day and Night 2; in Night 1 let the cold screen shift the highlights, but never make the skin grey-green in the mid-tones. Avoid beauty-smoothing; keep pore texture.
**Grain & texture:** 35 mm fine grain (Resolve Film Grain: 35 mm, strength 8 day / 12 night, saturation 0); Halation (radius small, strength 0.2) on the practicals only; no sharpening (≤ 0.1).

## Logo reveal

- S09: the lockup fades in with the standard text enter, 600 ms after the headline. No logo animation of its own.
- S17: the lockup enters at 00:41.00 on the first note of the sonic logo. The logo tile never scales, glows or rotates.

## End-card layout (16:9 1920×1080)

| Element | Center-x | y (top of block) | Size |
|---|---|---|---|
| Headline line 1 "העסק מכר." | 960 | 332 → 290 at 00:41.00 | 84 px, 600 |
| Headline line 2 "אתם כבר **בתמונה**." | 960 | 432 → 390 | 84 px, 600, "בתמונה" mint |
| Lockup (tile 88 px + name) | 960 | 560 | name 40 px |
| CTA button "פתיחת חשבון ←" | 960 | 700 | pill 64 px high, label 30 px |
| URL | 960 | 800 | 26 px |

- **Exact CTA:** **פתיחת חשבון** → `sydney-revenue-manager.vercel.app`
- **End-card duration:** 6.50 s (00:38.50–00:45.00); CTA readable for 3.50 s.

## Platform-safe margins

- 16:9: title-safe 10% on every side (text never beyond x 192–1728 / y 108–972).
- 9:16 (Reels/Stories): keep the top 14% (0–269 px), the bottom 35% (1248–1920 px) and 6% at the sides (65 px) free of text/logo/CTA.
- 1:1: 8% on every side.

## Accessibility captions

The film contains no speech, so no dialogue subtitles are required. Descriptive (SDH) captions for sound are provided as a sidecar file, **not burned in**: `exports/main/sydney-45s-16x9.he.srt` (e.g. "[צפצוף מסוף תשלום]", "[שקט]", "[מוזיקה שקטה ומתגברת]"). Contrast of all burned-in text ≥ 4.5:1; no flashing content; the end-card text is also stated in the video's post copy for screen readers.

## Export settings

| Deliverable | Codec | Resolution / fps | Bitrate | Audio |
|---|---|---|---|---|
| Master (archive) | ProRes 422 HQ | 1920×1080 (or 3840×2160) 24p | — | 48 kHz / 24-bit PCM stereo |
| Website hero | H.264 High 4.2 (+ VP9 WebM) | 1920×1080 24p | VBR 2-pass, target 10 Mbps, max 14 | AAC-LC 320 kbps 48 kHz (the page autoplays muted; the film is designed to read silently) |
| Meta 9:16 | H.264 High | 1080×1920 24p | target 12 Mbps | AAC 320 kbps |
| Meta 1:1 | H.264 High | 1080×1080 24p | target 10 Mbps | AAC 320 kbps |
| Cutdowns | H.264 High | as above | target 12 Mbps | AAC 320 kbps |

All: −14 LUFS integrated, ≤ −1 dBTP, Rec.709 / sRGB tags (`colr` = 1-1-1), `+faststart` for web playback, first frame = a meaningful frame (the card tap) and a separate poster frame exported from 00:43.50.
