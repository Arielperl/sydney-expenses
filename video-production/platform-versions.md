# Platform Versions

All versions keep: no voice, the same text system, the same sonic logo, and the same CTA **פתיחת חשבון** → `sydney-revenue-manager.vercel.app`.

---

## 1. Main 16:9 — 45.00 s (website hero, YouTube, LinkedIn)

Exactly as `script-and-timeline.md`. Rendered animatic: `exports/main/sydney-45s-16x9-animatic.mp4`.

---

## 2. Main 9:16 — 45.00 s (Instagram/Facebook Reels, Stories)

**Same timeline and cut points as the master** (so the music conforms 1:1). Composition is adapted, not cropped blindly.

| Shot | Method for 9:16 | Reframing |
|---|---|---|
| S01/S10, S02, S04 | Crop from the 16:9 generation (generate at 4K if possible) | Crop window centered on the terminal (the terminal sits on the 16:9 left third → crop x ≈ 18–50%) |
| S03 | **Native 9:16 generation** (same prompt + "vertical composition: counter and client in the lower half, the owner at a reformer above/behind, the plaster wall in the top third") | Text on the wall at y 16–26% |
| S05, S13, S16 | **Native 9:16 generations** from vertical versions of R3/R4, locked identically to each other | The counter at y 52–72%; the lamp above the counter; the window-light grid in the bottom 25%; the dark wall at y 14–35% for "23:40" |
| S06 | Crop (top-down works vertically: notebook centered, phone below) | — |
| S07, S15 | Crop (face on the 16:9 right third → centered) | Face center at y ≈ 45% |
| S08 | Crop centered on the shoulder/screen glow | Text at y 16–26% |
| S09, S11, S12, S14, S17 | Re-laid-out motion graphics | Headline on top (y 15–30%, centered/right-aligned), UI panel below (y 33–78%), full width minus 6% margins |

- **Text:** identical copy; headline size 76 px (of 1080 width); T3 breaks as "כמה באמת / נכנס היום?".
- **Safe zones:** top 14% / bottom 35% / sides 6% free of text, logo and CTA. The end-card CTA sits at y ≈ 60%, the URL at y ≈ 64%.
- **Music / SFX:** identical to the master.
- **End card:** 6.50 s; stacked: headline → lockup → button → URL.
- Rendered animatic: `exports/vertical/sydney-45s-9x16-animatic.mp4`.

---

## 3. Square 1:1 — 45.00 s (Facebook/Instagram feed)

Specified, not rendered in this package (it's derived from the 9:16 and 16:9 masters in the edit).

- Live action: crop from the 16:9 generation, keeping the subject on the center line (S03: crop x 22–78%; master wides: x 20–76% so the owner and lamp stay in).
- Motion graphics: headline above the panel (as in 9:16) with the panel at 84% width; headline 64 px.
- Safe margin 8%. Same timing, music and end card (6.50 s).

---

## 4. 15-second cutdown (Meta in-feed, pre-roll)

One idea: "problem → it arrives by itself → promise".

| Timecode | Shot (source) | On-screen text | Sound |
|---|---|---|---|
| 00:00.00–00:01.50 | S01 (source 00:00.00–00:01.50) | — | Beep 1 at 00:00.50 |
| 00:01.50–00:03.50 | S05 (source 00:08.50–00:10.50) | **23:40** 00:01.75–00:03.50 | Night drone in; J-cut hum 0.2 s before |
| 00:03.50–00:05.50 | S08 (source 00:15.25–00:17.25) | **כמה באמת נכנס היום?** 00:03.65–00:05.50 | Drone sweep |
| 00:05.50–00:06.25 | Black | — | **Silence** |
| 00:06.25–00:09.25 | S11 (the row lands at 00:06.45) | **מכירה חדשה. עדכון אוטומטי.** 00:06.60–00:09.10 | UI tick E6 at 00:06.45; the pulse starts |
| 00:09.25–00:10.75 | S12 (the figure eases 00:09.40–00:10.60) | — (the "נתונים להמחשה" pill stays) | Bass in, settle 00:10.60 |
| 00:10.75–00:11.75 | S15 (the lid closes; source 00:35.25–00:36.25) | — | Lid thock 00:11.60 |
| 00:11.75–00:15.00 | S17 compressed | **העסק מכר.** 00:11.85 · **אתם כבר בתמונה.** 00:12.30 · lockup + **פתיחת חשבון** + URL 00:12.75 | Sonic logo 00:12.75 / 13.00 / 13.25 / chord 13.50 |

- **Shots preserved:** S01, S05, S08, S11, S12, S15, S17. **Removed:** S02–S04, S06, S07, S09, S10, S13, S14, S16.
- **End card:** 3.25 s (CTA visible for 2.25 s; the Meta ad's own CTA button reinforces it).
- **Music edit:** the day section is removed; night drone → silence → the discovery section from the pulse start → the end-card swell and sonic logo, cut on bar lines.
- Rendered animatics: `exports/cutdowns/sydney-15s-16x9-animatic.mp4`, `exports/cutdowns/sydney-15s-9x16-animatic.mp4`.

---

## 5. 6-second hook (bumper / Stories)

| Timecode | Shot | Text | Sound |
|---|---|---|---|
| 00:00.00–00:01.25 | S01 | — | Beep 1 at 00:00.50 |
| 00:01.25–00:02.75 | S11 (the row lands at 00:01.45) | — | UI tick at 00:01.45 |
| 00:02.75–00:06.00 | S17 compressed | **העסק מכר.** 00:02.85 · **אתם כבר בתמונה.** 00:03.25 · lockup + **פתיחת חשבון** 00:04.00 (the URL is dropped in the 6 s cut; the ad link carries it) | Sonic logo 00:04.00 / 04.20 / 04.40 / chord 04.60 |

- **Removed:** everything except S01, S11 and S17.
- **Music:** the beep → UI tick → sonic logo only (no bed until the end-card chord).
- **End card:** 3.25 s.
- Rendered animatics: `exports/cutdowns/sydney-06s-9x16-animatic.mp4`, `exports/cutdowns/sydney-06s-16x9-animatic.mp4`.
