#!/usr/bin/env bash
# Rebuilds every animatic, temp score and storyboard frame from source.
# Requires: Google Chrome, Node 22+, Python 3 with numpy, ffmpeg. Run from video-production/.
set -euo pipefail
cd "$(dirname "$0")/.."

for cut in main 15 06; do python3 tools/score.py "$cut" "assets/music/temp-score-$cut.wav"; done

node tools/render.mjs --fmt 16x9 --cut main --audio assets/music/temp-score-main.wav --out exports/main/sydney-45s-16x9-animatic.mp4
node tools/render.mjs --fmt 9x16 --cut main --audio assets/music/temp-score-main.wav --out exports/vertical/sydney-45s-9x16-animatic.mp4
node tools/render.mjs --fmt 16x9 --cut 15   --audio assets/music/temp-score-15.wav   --out exports/cutdowns/sydney-15s-16x9-animatic.mp4
node tools/render.mjs --fmt 9x16 --cut 15   --audio assets/music/temp-score-15.wav   --out exports/cutdowns/sydney-15s-9x16-animatic.mp4
node tools/render.mjs --fmt 9x16 --cut 06   --audio assets/music/temp-score-06.wav   --out exports/cutdowns/sydney-06s-9x16-animatic.mp4
node tools/render.mjs --fmt 16x9 --cut 06   --audio assets/music/temp-score-06.wav   --out exports/cutdowns/sydney-06s-16x9-animatic.mp4

node tools/render.mjs --fmt 16x9 --cut main --stilldir assets/generated/storyboard \
  --stills 0.4,2.2,5,8,10,12.6,14.8,16.9,19.2,23.5,27.5,30.5,33.6,35.8,37.4,43.5 \
  --names F01-S01,F02-S02,F03-S03,F04-S04,F05-S05,F06-S06,F07-S07,F08-S08,F09-S09,F10-S11,F11-S12,F12-S13,F13-S14,F14-S15,F15-S16,F16-S17
for f in assets/generated/storyboard/F*.png; do ffmpeg -hide_banner -loglevel error -y -i "$f" -q:v 3 "${f%.png}.jpg" && rm "$f"; done
ffmpeg -hide_banner -loglevel error -y -pattern_type glob -i 'assets/generated/storyboard/F*.jpg' \
  -vf "scale=640:360,tile=4x4:padding=8:color=white" -frames:v 1 -q:v 3 assets/generated/storyboard/contact-sheet.jpg
