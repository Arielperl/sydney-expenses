# On-Screen Copy — Final (Main Film 16:9)

One final version per element. No alternatives are left open.
Global style: IBM Plex Sans Hebrew; enter = 400 ms fade + 12 px rise (ease-out-quart); exit = 300 ms fade. Positions are measured from the **right** edge (RTL) and the top edge, as a % of frame width/height, for the text block's top-right corner unless stated otherwise.

---

### T1 — העסק מכר.
- **English (production reference):** "The business made a sale."
- **Timecode:** 00:04.00 → 00:06.75 (2.75 s) · **Minimum reading:** 1.2 s
- **Purpose:** Name what we're watching; plant the first half of the brand line that closes the film.
- **Position / alignment:** top-right, x 10% / y 17%; right-aligned
- **Font / weight / size:** Plex Sans Hebrew 600, 64 px (headline tier)
- **Color / contrast:** ink `#151A19` (brand zinc-900) directly on the bright plaster wall, no scrim — the only dark-ink text in the film, because it is the only text over a bright day frame (contrast ≈ 14:1 on `#EFE9DF`)
- **Entry / exit:** standard enter / standard exit
- **Relation to action:** appears 0.25 s after the third beep, as the client turns to leave
- **Sound cue:** lands on the downbeat chord (Beep 3 = G♯5 → E add9 chord)

### T2 — 23:40
- **English:** "11:40 pm"
- **Timecode:** 00:08.75 → 00:11.00 (2.25 s) · **Minimum reading:** 0.8 s
- **Purpose:** Time anchor for the "same evening" device.
- **Position / alignment:** top-right, x 10% / y 12%; right-aligned
- **Font / weight / size:** IBM Plex Sans 500, tabular figures, 30 px, tracking +4%
- **Color / contrast:** mint #41D7B2 on the dark wall (contrast > 7:1)
- **Entry / exit:** standard
- **Relation to action:** appears as the wide settles on her hunched posture
- **Sound cue:** none (the distant scooter starts 0.75 s later) — deliberately unaccented

### T3 — כמה באמת נכנס היום?
- **English:** "How much actually came in today?"
- **Timecode:** 00:15.50 → 00:17.50 (2.0 s; cut away by the hard cut to black) · **Minimum reading:** 1.6 s
- **Purpose:** State the problem as the audience's own question.
- **Position / alignment:** top-right, x 10% / y 17%; right-aligned
- **Font / weight / size:** 600, 64 px
- **Color / contrast:** #FFFFFF with radial scrim 35%
- **Entry / exit:** standard enter; **no exit animation** — disappears with the hard cut to black
- **Relation to action:** appears as she leans back from the laptop
- **Sound cue:** under the drone's filter sweep; the cut to silence ends it

### T4 — אותו יום.  + lockup
- **English:** "The same day." + "Revenue Manager / by SYDNEY"
- **Timecode:** headline 00:18.00 → 00:19.70; lockup 00:18.60 → 00:19.70 · **Minimum reading:** 1.0 s
- **Purpose:** The turn. Introduces the brand as the guide, without a slogan.
- **Position / alignment:** headline centered x 50% / y 44%; lockup centered y 60%; center-aligned
- **Font / weight / size:** headline 600, 72 px; lockup: logo tile 64 px + "מנהל הכנסות" 600 32 px + "מבית SYDNEY" 500 13 px small caps, tracking 16%, 60% white
- **Color / contrast:** white on black
- **Entry / exit:** standard (lockup enters 600 ms after the headline); both fade 300 ms
- **Relation to action:** black screen after Night 1
- **Sound cue:** absolute silence until 00:18.60, then one felt-piano E5 with the lockup

### T5 — מכירה חדשה. עדכון אוטומטי.  / sub: חיבור ישיר ל-Grow ול-Cardcom
- **English:** "New sale. Automatic update." / "Direct connection to Grow and Cardcom"
- **Source:** website feature title (`HomePage.tsx` features[1]) and connections section
- **Timecode:** headline 00:21.75 → 00:24.50 (2.75 s); sub 00:22.25 → 00:24.50 (2.25 s) · **Minimum reading:** 1.6 s / 1.8 s
- **Purpose:** The mechanism in 4 words; the proof in the sub-line.
- **Position / alignment:** right third, x 8% / y 38%; right-aligned; sub 20 px below the headline
- **Font / weight / size:** headline 600 60 px (two lines: "מכירה חדשה." / "עדכון אוטומטי."); sub 400 30 px
- **Color / contrast:** headline white; sub white 72%; on the deep-green backdrop (contrast > 10:1)
- **Entry / exit:** standard, lines staggered 120 ms; sub enters 500 ms after the headline
- **Relation to action:** enters 0.25 s after the new sale row lands
- **Sound cue:** the UI "tick" (E6) at 00:21.50 precedes it
- **Bidi note:** "ל-Grow" and "ול-Cardcom": Hebrew prefix + hyphen + Latin word; render inside an RTL paragraph (`dir="rtl"`), no manual reordering. Verified rendering: "חיבור ישיר ל-Grow ול-Cardcom" reads right-to-left with the Latin brand names intact.

### T6 — התמונה המלאה, במבט אחד.
- **English:** "The full picture, at a glance."
- **Source:** website feature title (`HomePage.tsx` features[0])
- **Timecode:** 00:25.00 → 00:28.75 (3.75 s) · **Minimum reading:** 1.6 s
- **Purpose:** The benefit of the figure the viewer just watched update.
- **Position / alignment:** right third, x 8% / y 38%; right-aligned; two lines ("התמונה המלאה," / "במבט אחד.")
- **Font / weight / size:** 600, 60 px
- **Color / contrast:** white on deep green
- **Entry / exit:** standard, lines staggered 120 ms
- **Relation to action:** appears just before the net figure eases to its new value
- **Sound cue:** the bass entry at 00:25.25

### T7 — 23:40 (repeat)
- **English:** "11:40 pm"
- **Timecode:** 00:29.25 → 00:31.25 (2.0 s)
- **Purpose:** Proves it's the same evening. **Must be pixel-identical to T2** in position, size, color and animation.
- **Position / font / color / animation:** as T2
- **Sound cue:** none (the warm chord is already sounding)

### T8 — יודעים מה דורש טיפול.
- **English:** "You know what needs attention."
- **Source:** website feature title (`HomePage.tsx` features[2])
- **Timecode:** 00:31.75 → 00:34.00 (2.25 s) · **Minimum reading:** 1.4 s
- **Purpose:** Second benefit — only what needs her.
- **Position / alignment:** right third, x 8% / y 38%; right-aligned; two lines ("יודעים מה" / "דורש טיפול.")
- **Font / weight / size:** 600, 60 px
- **Color / contrast:** white on deep green
- **Entry / exit:** standard
- **Relation to action:** precedes the click that resolves the first item
- **Sound cue:** trackpad click 00:32.50

### T9 — העסק מכר. / אתם כבר בתמונה.
- **English:** "The business made a sale. / You're already in the picture."
- **Source:** website hero headline (`HomePage.tsx` `<h1>`), including the mint emphasis on "בתמונה"
- **Timecode:** line 1 00:38.75 → 00:45.00; line 2 00:39.50 → 00:45.00 · **Minimum reading:** 2.0 s
- **Purpose:** Closes the loop opened by T1; the brand promise.
- **Position / alignment:** centered x 50%; y 36% (moves to y 30% at 00:41.00 with a 600 ms ease-out-quart to make room for the lockup); center-aligned
- **Font / weight / size:** 600, 84 px, line-height 1.15
- **Color / contrast:** white; "בתמונה" mint #41D7B2; background deep green with the wave at 22% opacity kept away from the text area
- **Entry / exit:** standard enter for each line; no exit (film ends on it)
- **Sound cue:** end swell starting 00:38.50; line 2 on a soft piano note

### T10 — Lockup + CTA + URL
- **Hebrew:** מנהל הכנסות / מבית SYDNEY · button: **פתיחת חשבון ←** · URL: **sydney-revenue-manager.vercel.app**
- **English:** "Revenue Manager / by SYDNEY" · "Open an account" · URL
- **Timecode:** lockup 00:41.00 → 00:45.00; button + URL 00:41.50 → 00:45.00 · **Minimum reading:** 3.0 s (achieved: 3.5 s)
- **Purpose:** Brand recall and the one action.
- **Position:** lockup centered y 58%; button centered y 72%; URL centered y 81%
- **Font / weight / size:** lockup tile 88 px + "מנהל הכנסות" 600 40 px + "מבית SYDNEY" 500 16 px (tracking 16%); button label 600 30 px in a 64 px-high mint (#41D7B2) pill with 12 px radius, label color #062B23, arrow "←" after the label (points in the RTL reading direction, as on the website); URL IBM Plex Sans 500 26 px, white 80%, `dir="ltr"` isolated
- **Entry / exit:** standard; the button enters 120 ms before the URL; no exit
- **Sound cue:** sonic logo — B4 00:41.00, E5 00:41.25, G♯5 00:41.50, E major chord 00:41.75

---

## In-product UI copy (motion-graphics inserts) — exact strings from the product

| Insert | Strings (Hebrew, as in `translation.json` / `HomePage.tsx`) | English reference |
|---|---|---|
| S11 מכירות | מכירות · היום · שיעור פרטי · ₪180.00 · Cardcom · הצליחה · ממתין למסמך מהספק · 16:12 · כרטיסייה 10 שיעורים · ₪650.00 · Grow · 11:05 · מסמך הופק · שיעור קבוצתי · ₪65.00 · Grow · 09:30 · מסמך הופק · נתונים להמחשה | Sales · Today · Private lesson · succeeded · waiting for provider document · 10-class card · document issued · Group class · illustrative data |
| S12 סיכום התקופה | סיכום התקופה · נתונים להמחשה · ספטמבר · תקבולים נטו לאחר ניכויים · ₪24,701.24 → ₪24,850.00 · ברוטו בניכוי מע״מ, עמלות והחזרים. אינו רווח ואינו יתרת חשבון. · הכנסה ברוטו ₪30,440.00 → ₪30,620.00 · מע״מ הכלול בברוטו ₪4,643.39 → ₪4,670.85 · עמלות סליקה ₪639.24 → ₪643.02 · החזרים חלקיים ₪456.13 | Period summary · illustrative · September · Net receipts after deductions · "Gross minus VAT, fees and refunds. Not profit and not a bank balance." · Gross revenue · VAT included in gross · Processing fees · Partial refunds |
| S14 דורש טיפול | דורש טיפול · 2 → 1 · מכירות שדורשות פעולה · מסמך ממתין · אימון זוגי · ₪320.00 · 21.9 · ייבוא מסמך · בדיקת מע״מ · כרטיסייה 10 שיעורים · ₪650.00 · 3.9 · פרטי מכירה · טופל | Needs attention · sales requiring action · Document pending · Duet session · Import document · VAT review · 10-class card · Sale details · Handled |

Note on "טופל" ("Handled"): used only as a transient confirmation label in the animation; the real product removes a resolved sale from the list, which is exactly what the animation shows next.

## Hebrew proofreading record

- ✅ Gershayim in מע״מ uses U+05F4 (״), matching the product.
- ✅ Final periods on declarative lines; question mark on T3 only.
- ✅ Currency shown as ₪ followed by the number with two decimals and a comma thousands separator, inside an LTR isolate (`<bdi>`), matching the website's preview.
- ✅ "23:40" and the URL are LTR isolates inside RTL layout.
- ✅ No gendered verb forms in the viewer-facing copy except the plural "אתם" / "יודעים", which match the website's register.
- ✅ No English words except the brand/provider names SYDNEY, Grow, Cardcom (as on the website).
