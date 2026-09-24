#!/usr/bin/env bash
# Rebuilds every version, temp score and storyboard frame of "מרעש לבהירות" from source.
# Requires: Google Chrome, Node 22+, Python 3 with numpy, ffmpeg. Run from anywhere.
set -euo pipefail
cd "$(dirname "$0")/.."

for cut in main 15 06; do python3 tools/score.py "$cut" "assets/music/temp-score-$cut.wav"; done

render() { node tools/render.mjs --mb 6 --fmt "$1" --cut "$2" --audio "assets/music/temp-score-$3.wav" --out "$4"; }
render 16x9 main main exports/main/sydney-30s-16x9.mp4
render 9x16 main main exports/vertical/sydney-30s-9x16.mp4
render 16x9 15   15   exports/cutdowns/sydney-15s-16x9.mp4
render 9x16 15   15   exports/cutdowns/sydney-15s-9x16.mp4
render 16x9 06   06   exports/cutdowns/sydney-06s-16x9.mp4
render 9x16 06   06   exports/cutdowns/sydney-06s-9x16.mp4

node tools/render.mjs --fmt 16x9 --cut main --stilldir assets/generated/storyboard \
  --stills 0.12,1.6,3.0,5.3,6.9,8.18,9.5,12.8,15.2,19.9,23.9,25.6,28.8 \
  --names F01-A1,F02-A1,F03-A2,F04-B,F05-B,F06-C,F07-C,F08-D,F09-E,F10-F,F11-G,F12-H1,F13-H2
for f in assets/generated/storyboard/F*.png; do ffmpeg -hide_banner -loglevel error -y -i "$f" -q:v 3 "${f%.png}.jpg" && rm "$f"; done
ffmpeg -hide_banner -loglevel error -y -pattern_type glob -i 'assets/generated/storyboard/F*.jpg' \
  -vf "scale=640:360,tile=4x4:padding=8:color=white" -frames:v 1 -q:v 3 assets/generated/storyboard/contact-sheet.jpg
