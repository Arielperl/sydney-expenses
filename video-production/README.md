# Video production — "אותו ערב, פעמיים" (Same Evening, Twice)

A 45-second, dialogue-free explainer for **מנהל הכנסות מבית Sydney**, plus 9:16, 15 s and 6 s versions.

## Read in this order

1. `project-analysis.md` — what the project confirms, what the film must not claim
2. `creative-brief.md` → `concepts.md` → `selected-concept.md`
3. `visual-continuity-bible.md` — locked characters, props, location, light, type
4. `script-and-timeline.md` · `on-screen-copy.md` · `storyboard.md` · `shot-list.md`
5. `generation-prompts.md` — AI still + video prompts (reference plates R1–R5, shots S01–S16)
6. `sound-design.md` · `editing-plan.md` · `platform-versions.md` · `production-checklist.md`

## What is already rendered

| File | What it is |
|---|---|
| `exports/main/sydney-45s-16x9-animatic.mp4` | Full-length animatic: final typography, UI motion graphics, end card, temp score; live-action shots are labelled **PREVIS** placeholders |
| `exports/vertical/sydney-45s-9x16-animatic.mp4` | Vertical animatic |
| `exports/cutdowns/sydney-15s-{16x9,9x16}-animatic.mp4` | 15 s cutdown |
| `exports/cutdowns/sydney-06s-{9x16,16x9}-animatic.mp4` | 6 s hook |
| `exports/main/sydney-45s-16x9.he.srt` | Descriptive (SDH) sidecar captions in Hebrew |
| `assets/generated/storyboard/` | 16 storyboard frames + contact sheet |
| `assets/music/temp-score-*.wav` | Synthesized temp score + sound design (−14 LUFS). Temp only |

## Rebuild

```bash
video-production/tools/build.sh
```

Needs Google Chrome, Node 22+, Python 3 + numpy and ffmpeg. `tools/film.html` is the film itself (open it in a browser with `?fmt=16x9&cut=main&still=27.5` to inspect a frame); `tools/render.mjs` captures it frame by frame; `tools/score.py` synthesizes the audio. Fonts (IBM Plex Sans Hebrew) load from Google Fonts, exactly as on the website.

Original brand files were copied into `assets/source/`, never modified.
