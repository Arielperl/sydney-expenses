# Production Checklist (v2)

`[x]` = done in this package · `[ ]` = remaining.

## Business and claims
- [x] Product name, lockup and domain confirmed (`www.sydneyexpenses.com`)
- [x] Film text matches the website messaging of 2026-09-25 (eyebrow מנהל הכנסות לעסקים; headline מכירות, הכנסות ומה שדורש טיפול. במקום אחד.); no earlier slogans remain
- [x] Automatic capture claimed only for connected Grow/Cardcom; CSV is not called automatic
- [x] Net figure shown with the product's own "אינו רווח ואינו יתרת חשבון" line
- [x] The assistant answer quotes net receipts from the same illustrative data
- [x] No statistics, testimonials, prices, awards, guarantees; every panel says "נתונים להמחשה"
- [x] Figures reconcile exactly (`visual-continuity-bible.md` §6)
- [ ] Client confirms self-serve sign-up is open (the site FAQ mentions a rollout stage)
- [ ] Client OK with naming Grow and Cardcom (text only, no logos) in paid ads
- [ ] Legal/marketing sign-off

## Brand
- [x] Colors, typeface and UI tokens taken from the product (`index.css`, `PublicPages.css`)
- [x] Logo unaltered, always on the pale tile
- [ ] Client approves the sonic logo (B4–E5–G♯5 → E major)

## Assets
- [x] Only existing project assets used (logo SVG, hero texture, product strings); originals untouched
- [x] No AI footage, no actors, no placeholders

## Motion graphics and edit
- [x] 30 s film built on the 120 BPM grid; 6-sample motion blur
- [x] 16:9, 9:16, 15 s ×2, 6 s ×2 rendered
- [x] Hebrew RTL, gershayim, bidi isolation verified in renders
- [ ] Native-speaker read of the final renders
- [ ] Optional: capture the real app (dark theme, demo workspace) to cross-check the rebuilt panels

## Audio
- [x] Temp score synthesized (no third-party material), −14 LUFS, ≤ −1 dBTP, digital silence at 7.75–8.00
- [ ] Final music: commission or license a track for paid ads, conformed to the cue points in `sound-design.md`
- [ ] Final SFX from a licensed library (or keep the synthesized UI sounds)

## Accessibility and platforms
- [x] Hebrew SDH sidecar captions (`exports/main/sydney-30s-16x9.he.srt`)
- [x] 9:16 text inside the Reels safe zones (y 270–1250)
- [x] No flashing above 3 Hz (the drop flash is a single 0.45 s pulse)
- [ ] Check the 9:16 in the Meta ads preview tool
- [ ] 1:1 version (specified, not rendered)

## Delivery
- [x] Files named `sydney-{duration}-{ratio}.mp4`
- [ ] Upload: the website hero (16:9, autoplay muted — the film reads without sound), Meta (9:16 + 15 s/6 s)
