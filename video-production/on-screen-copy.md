# On-Screen Copy — Final (v2, "מרעש לבהירות", 30 s)

One final version per element. Global system: IBM Plex Sans Hebrew 700 for headlines. Entry is a **mask reveal**: each line slides up from behind its own clip line over 0.55 s (expo-out), with lines staggered 0.08 s. Exit slides up and out over 0.28 s (quart-in). Right-aligned (RTL) except the centered hero lines. Positions are for 16:9; the 9:16 values are in `platform-versions.md`.

| # | Hebrew (exact) | English (production reference) | In → out | Reading time | Purpose | Position / align | Font / weight / size | Color & contrast | Sound cue | Source |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ₪180 · ₪65 · ₪650 · ₪320 (no source tags; removed 2026-09-25) | The day's sales | 0.00 / 0.50 / 1.00 / 1.50 → recede | — (visual) | Hook: sales, visually | Center + around, in depth | IBM Plex Sans 600, 190 px | Warm white on near-black; later amounts dimmer/blurred | A tuned beep per hit | Illustrative |
| 2 | **מכירות, הכנסות** (9:16: **מכירות,** / **הכנסות**) | Sales, revenue | 2.00 → 3.72 | 1.7 s (min 1.0) | Names the moment; opens the website headline | Center, y 420 px (9:16: two lines from y 745) | 700, 180 px (9:16: 150 px) | White; amounts behind dim to 25% | Stab + soft impact at 2.00 | Website headline, line 1 |
| 3 | כמה עמלות? · איפה הקבלה? · מה עם המע״מ? · ומה עם ההחזרים? | How much in fees? · Where's the receipt? · What about VAT? · And the refunds? | 4.00 / 4.50 / 5.00 / 5.50 → dim from 6.0, swept at 8.0 | 0.5–2 s each (texture, then context) | The noise: questions owners actually have | Scattered in the four quadrants | 600, 58 px | Light grey `#E9EEEC`, jittering | Dissonant cluster on each | Problem framing (no claim) |
| 4 | **כמה באמת נכנס?** | How much actually came in? | 6.00 → swept at 8.00 | 1.75 s + a 0.25 s freeze | The problem in one question | Center, y 440 px | 700, 150 px, dark halo `0 4px 40px rgba(0,0,0,.55)` | White; receipts behind dim to 30% and blur | Impact at 6.00; riser; silence at 7.75 | — |
| 5 | **מנהל הכנסות** / **לעסקים** | Revenue manager / for businesses | 8.30 → 9.85 | 1.55 s (min 1.2) | The turn; names what the product is | Right third: right 110 px, top 340 px, width 680 | 700, 84 px; line 2 mint `#41D7B2` | White/mint on deep green | THE DROP at 8.00 | Website eyebrow (2026-09-25) |
| 6 | Lockup: מנהל הכנסות / מבית SYDNEY | Revenue Manager / by SYDNEY | 9.10 → 9.85 | 0.75 s (a recognition flash; it returns at the end) | Brand enters as the guide | Under #5 | Tile 66 px + name 600 30 px + "מבית SYDNEY" 500 12 px, tracked 16% | Logo on the pale tile | — | Brand |
| 7 | **מכירה חדשה.** / **עדכון אוטומטי.** | New sale. / Automatic update. | 10.10 → 13.70 | 3.6 s | Mechanism | Right third | 700, 84 px | White | Row ticks 10.5/11.5/12.5 | Website feature title |
| 8 | *(removed 2026-09-25 at the client's request)* | — | — | — | — | — | — | — | — | — |
| 9 | **התמונה המלאה,** / **במבט אחד.** | The full picture, / at a glance. | 14.30 → 17.70 | 3.4 s | Benefit of the figure | Right third | 700, 84 px | White | Chime at 15.80 | Website feature title |
| 10 | **יודעים מה** / **דורש טיפול.** | You know what / needs attention. | 18.30 → 21.70 | 3.4 s | Control | Right third | 700, 84 px | White | Click 19.50 | Website feature title |
| 11 | **שואלים את** / **הנתונים שלכם.** | Ask / your own data. | 22.30 → 24.75 | 2.45 s | The assistant | Right third | 700, 84 px | White | Answer chime 23.80 | Website feature title |
| 12 | **מכירות, הכנסות** / **ומה שדורש טיפול.** / **במקום אחד.** | Sales, revenue / and what needs attention. / In one place. | 26.00 / 26.30 / 26.60 → end | 3.4 s after the last line (min 2.2) | The complete website headline; completes the line opened by #2 | Center, top 270 → 210 px at 27.10 (9:16: 640 → 570 px) | 700, 96 px (9:16: 100 px); "במקום אחד." in mint | White/mint on dimmed panels (radial darkening 60%) | Piano chord 26.00 | Website headline (2026-09-25) |
| 13 | Lockup | — | 27.25 → end | 2.75 s | Brand recall | Center, y 610 | Tile 88 px + name 40 px | — | Sonic logo starts 27.25 | Brand |
| 14 | **פתיחת חשבון ←** | Open an account | 27.50 → end | 2.5 s | The one action | Center, y 750 | 600, 32 px in a mint pill (`#41D7B2`, text `#062B23`), mint glow; pops with a slight overshoot | ≈ 9:1 contrast | Chord 28.00 | Website CTA |
| 15 | www.sydneyexpenses.com | — | 27.62 → end (not in the 6 s cut) | 2.4 s | Where to go | Center, y 860 | IBM Plex Sans 500, 28 px, LTR-isolated | White 82% | — | Client-confirmed domain (updated 2026-09-25) |

## In-product UI strings (exact, from `frontend/src/i18n/locales/he/translation.json` and `HomePage.tsx`)

מכירות · היום · הצליחה · ממתין למסמך מהספק · מסמך הופק · נתונים להמחשה · סיכום התקופה · תקבולים נטו לאחר ניכויים · ברוטו בניכוי מע״מ, עמלות והחזרים. אינו רווח ואינו יתרת חשבון. · הכנסה ברוטו · מע״מ הכלול בברוטו · עמלות סליקה · החזרים חלקיים · דורש טיפול · מכירות שדורשות פעולה · מסמך ממתין · בדיקת מע״מ · ייבוא מסמך · פרטי מכירה · עוזר AI · שאל שאלות על המכירות וההכנסות שלך · שאל שאלה... · כמה הכנסתי החודש?

Illustrative assistant answer (not a product string): "בספטמבר נכנסו ₪24,850.00 נטו, לאחר מע״מ, עמלות סליקה והחזרים." It names net receipts, consistent with the assistant's gross/net/profit rules in `README.md`.

## Hebrew proofreading record

- ✅ Gershayim in מע״מ use U+05F4 (״).
- ✅ Question marks and periods sit at the visual left end (RTL rendering verified in renders).
- ✅ ₪ amounts, times, "23:40"-style digits and the URL are LTR-isolated (`<bdi>` / `unicode-bidi: isolate`).
- ✅ The plural register (אתם / יודעים / שואלים / שלכם) matches the website.
- ✅ The only Latin text is the brand/provider names SYDNEY, Grow, Cardcom, CSV.
