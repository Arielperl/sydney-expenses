# Selected Concept — "מרעש לבהירות" (From Noise to Clarity)

**Status:** v2, the current direction. **Text revision 2026-09-25:** the on-screen slogans were updated to the new website messaging; scenes, timing, motion, audio and visuals are unchanged. It replaces v1, "אותו ערב, פעמיים", which the client rejected on 2026-09-24: the cartoon previs didn't work and the story didn't grab.
**Client decisions (v2 brief):** premium motion design, no people and no placeholders · punchy and fast · 30 s main film · website + Meta ads · CTA → `sydney-revenue-manager.vercel.app`.

## Logline

Sales slam onto the screen to the beat and pile up into noise: amounts, receipts, questions. Then a single mint line sweeps through, and everything snaps into place inside the product.

## The one message

**מכירות, הכנסות ומה שדורש טיפול. במקום אחד.** Your sales arrive and organize themselves; you see what came in, what needs you, and you can just ask.
The film closes on the website's headline (updated 2026-09-25): **מכירות, הכנסות / ומה שדורש טיפול. / במקום אחד.**

## Why this works

- **Punchy by construction:** the edit is locked to a 120 BPM grid, with every sale a beat and every beep a note.
- **The before/after is one gesture:** chaos → a mint sweep → order. It reads instantly with the sound off.
- **The product is the hero:** four real features in four bars, using the product's own Hebrew UI strings, tokens and typeface.
- **Fully producible in-house:** HTML/CSS motion design rendered frame-accurately with motion blur. There's no AI footage, no actors and no continuity risk.

## Structure (30.0 s · 120 BPM · 1 bar = 2 s)

| Section | Time | Bars | What happens |
|---|---|---|---|
| A · The sales | 0.00–4.00 | 1–2 | Amounts slam in on each beat (₪180 · ₪65 · ₪650 · ₪320), each with a tuned terminal beep and a source tag (Grow / Cardcom / CSV). On bar 2 they rain in on 8th notes. **מכירות, הכנסות** |
| B · The noise | 4.00–7.75 | 3–4 | Amounts go grey and jitter; receipts tumble; questions pop up (כמה עמלות? · איפה הקבלה? · מה עם המע״מ? · ומה עם ההחזרים?) over a riser, peaking on **כמה באמת נכנס?** |
| Gap | 7.75–8.00 | — | Freeze, with digital silence. |
| C · The drop | 8.00–10.00 | 5 | A mint line sweeps right → left and wipes the noise away. Four amounts fly into rows of the real **מכירות** list. **מנהל הכנסות לעסקים** + brand lockup. |
| D · Automatic | 10.00–14.00 | 6–7 | New sales land on the beat (Grow/Cardcom highlighted). **מכירה חדשה. עדכון אוטומטי.** |
| E · The number | 14.00–18.00 | 8–9 | Whip pan → סיכום התקופה. The net figure eases ₪24,701.24 → ₪24,850.00, the breakdown cascades and the chart draws. **התמונה המלאה, במבט אחד.** |
| F · Attention | 18.00–22.00 | 10–11 | Whip pan → דורש טיפול. A click on ייבוא מסמך → ✓ טופל → the count goes 2 → 1. **יודעים מה דורש טיפול.** |
| G · Ask | 22.00–25.00 | 12–13½ | Whip pan → עוזר AI. "כמה הכנסתי החודש?" is typed and answered. **שואלים את הנתונים שלכם.** |
| H · The picture | 25.00–30.00 | 13½–15 | All four panels fly into one composition, then dim. **מכירות, הכנסות / ומה שדורש טיפול. / במקום אחד.** · lockup · **פתיחת חשבון** · URL · sonic logo. |

## Claims (all confirmed; see `project-analysis.md` §13)

Automatic capture from connected Grow and Cardcom · a net figure with its breakdown and the product's own line "אינו רווח ואינו יתרת חשבון" · a needs-attention list · the AI assistant answering from the business's data. Every panel carries **נתונים להמחשה**; figures reconcile exactly (see `visual-continuity-bible.md` §6).

## Deliverables

| Version | File |
|---|---|
| 30 s · 16:9 | `exports/main/sydney-30s-16x9.mp4` |
| 30 s · 9:16 | `exports/vertical/sydney-30s-9x16.mp4` |
| 15 s · 16:9 / 9:16 | `exports/cutdowns/sydney-15s-{16x9,9x16}.mp4` |
| 6 s · 16:9 / 9:16 | `exports/cutdowns/sydney-06s-{16x9,9x16}.mp4` |
