# Production Checklist

`[x]` = done in this package · `[ ]` = remaining.

## Business-information verification
- [x] Product name and lockup confirmed ("מנהל הכנסות" / "מבית SYDNEY") — `HomePage.tsx`, `README.md`
- [x] Website domain confirmed by the client: `sydney-revenue-manager.vercel.app`
- [ ] Client confirms the product is open for self-serve sign-up (the FAQ mentions a rollout stage — "המוצר נמצא בשלב ההרצה")
- [ ] Client confirms that showing Grow and Cardcom by name (text only) is acceptable in paid ads

## Claims verification
- [x] Automatic capture only for connected Grow/Cardcom (confirmed); CSV is not described as automatic
- [x] Net receipts shown with the product's own "not profit, not a bank balance" line
- [x] No claim that Sydney issues invoices/receipts; the new sale shows "ממתין למסמך מהספק" (the product's real state)
- [x] No statistics, testimonials, prices, awards, guarantees
- [x] All amounts are the website's illustrative figures and carry "נתונים להמחשה"; the arithmetic reconciles (see bible §14)
- [ ] Legal/marketing sign-off on the final cut

## Brand review
- [x] Colors, typeface and motion curve are taken from `index.css` / `PublicPages.css`
- [x] The logo is used unaltered, always on the pale tile
- [ ] Client approves the logo-on-tile treatment in motion (end card)
- [ ] Client approves the sonic-logo idea (beeps B4–E5–G♯5)

## Asset collection
- [x] Logo SVG and hero texture copied to `assets/source/` (originals untouched)
- [x] `sydney-hero.png` rejected (garbled AI text)
- [ ] Reference capture of מכירות / לוח בקרה / דורש טיפול (dark theme, fictional demo workspace, 2× DPR)
- [ ] IBM Plex Sans Hebrew / Plex Sans font files installed on the editing machine (SIL Open Font License)

## Pre-production
- [x] Concept, script, storyboard, shot list, prompts, sound design, editing plan
- [ ] Budget and schedule for AI generation (≈ 11 shots × 3–4 takes + 5 reference plates + native 9:16 re-generations for 4 shots; price against the chosen tool's current plan)
- [ ] Choose the AI video tool(s) and plan (Veo 3 / Kling / Runway)

## Storyboard approval
- [x] Previs storyboard frames rendered (`assets/generated/storyboard/`)
- [x] Animatic rendered (16:9, 9:16, 15 s, 6 s)
- [ ] Client approval of the animatic before any paid generation

## Character continuity
- [ ] R1 character sheet generated and frozen
- [ ] Every OWNER shot checked against R1 (face, freckles, brows, hair bun, strands, necklace, hoops, hair tie on the left wrist, no rings)
- [ ] Night wardrobe identical across S05–S08, S13–S16 (cardigan oatmeal chunky-knit; slipping in Night 1, neat in Night 2)

## Product continuity
- [ ] Terminal identical in S01, S02, S03, S04 (shape, angle, position, mint glow only)
- [ ] Laptop has no logo and an unreadable screen in every shot
- [ ] Phone screen off by day, unreadable at night

## Practical filming (only if replacing any AI shot)
- [ ] Hand model(s) for S01/S02/S06 (a practical macro shoot is a cheap, high-quality alternative)
- [ ] Foley recording session (card, beep reference, lamp, pencil, paper, lid, door, mug)

## AI generation
- [ ] R1–R5 reference plates generated and approved
- [ ] Start frames approved per shot
- [ ] 3–4 takes per shot; selects logged
- [ ] Master wides S05/S13/S16 overlay-aligned (< 1%)
- [ ] S07/S15 framing matched
- [ ] All AI audio discarded
- [ ] Native 9:16 generations for S03, S05, S13, S16

## Screen capture
- [ ] Capture in a fictional demo workspace only — no real customer data
- [ ] The dark theme, Hebrew, 2× DPR; the cursor hidden (it's added in MG)

## Motion graphics
- [x] Reference animation for S09, S11, S12, S14, S17 built (`tools/film.html`)
- [ ] Final After Effects rebuild (or approve the HTML render as final for the MG shots)

## Text proofreading
- [x] Hebrew copy proofread (gershayim, punctuation, RTL, bidi isolation of ₪ figures, 23:40 and the URL)
- [ ] Native-speaker second read of the final render

## Music licensing
- [ ] Composer commissioned (recommended) or a library track licensed for paid ads; the license stored in `assets/music/`
- [x] The temp score is synthesized (no third-party material) — temp only

## Sound-effect licensing
- [ ] SFX from a royalty-free library or recorded foley; licenses stored in `assets/sound-effects/`

## Editing
- [ ] Conform AI shots into the animatic timeline (the same cut points)
- [ ] J/L-cuts and the silence at 00:17.50 respected

## Color grading
- [ ] Day / Night 1 / Night 2 looks per `editing-plan.md`
- [ ] Skin tones checked on the vectorscope; the terminal glow = `#41D7B2`

## Sound mixing
- [ ] −14 LUFS integrated, ≤ −1 dBTP
- [ ] Digital silence 00:17.50–00:18.60
- [ ] No intelligible speech anywhere (listen on headphones at +10 dB)

## Accessibility
- [x] SDH sidecar captions drafted (`exports/main/sydney-45s-16x9.he.srt`)
- [ ] Contrast of burned-in text ≥ 4.5:1 verified on the graded picture
- [ ] No flashing > 3 Hz

## Platform formatting
- [x] 16:9, 9:16, 15 s, 6 s animatics rendered; 1:1 specified
- [ ] 9:16 safe zones checked in the Meta ads preview tool

## Export
- [ ] ProRes master + H.264 deliverables per `editing-plan.md`
- [ ] Poster frame from 00:43.50

## Final review
- [ ] Watch muted: is the story clear?
- [ ] Watch with sound, eyes closed: does the audio arc work?
- [ ] Check every claim against `project-analysis.md` §13–14

## Delivery
- [ ] Files named `sydney-{duration}-{ratio}-{version}.mp4`
- [ ] Deliver the masters, stems (music / FX / ambience), project files, licenses
