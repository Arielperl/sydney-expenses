# Video production — "מרעש לבהירות" (From Noise to Clarity), v2

A 30-second, dialogue-free motion-design film for **מנהל הכנסות מבית Sydney**, plus 9:16, 15 s and 6 s versions. v1 ("אותו ערב, פעמיים") was rejected and is kept only in git history.

## Read in this order

1. `project-analysis.md`: what the project confirms and what the film must not claim
2. `creative-brief.md` → `concepts.md` → `selected-concept.md`
3. `visual-continuity-bible.md`: the motion design system (color, type, motion, data)
4. `script-and-timeline.md` · `on-screen-copy.md` · `storyboard.md` · `shot-list.md`
5. `sound-design.md` · `editing-plan.md` · `platform-versions.md` · `production-checklist.md`
6. `generation-prompts.md`: v2 needs no AI generation (explains why)

## Rendered files

| File | What |
|---|---|
| `exports/main/sydney-30s-16x9.mp4` | Main film, 1920×1080 |
| `exports/vertical/sydney-30s-9x16.mp4` | Vertical, 1080×1920 |
| `exports/cutdowns/sydney-15s-{16x9,9x16}.mp4` | 15 s |
| `exports/cutdowns/sydney-06s-{16x9,9x16}.mp4` | 6 s hook |
| `exports/main/sydney-30s-16x9.he.srt` | Hebrew SDH captions |
| `assets/generated/storyboard/` | Storyboard frames + contact sheet |

## Rebuild

```bash
video-production/tools/build.sh
```

This needs Google Chrome, Node 22+, Python 3 + numpy and ffmpeg. `tools/film.html` is the film (open it with `?fmt=16x9&cut=main&still=15.2` to inspect a frame); `tools/render.mjs` captures it with motion blur; `tools/score.py` synthesizes the temp score. Rendered MP4/WAV files are git-ignored.
