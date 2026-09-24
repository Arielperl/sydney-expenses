# Visual Continuity Bible — Motion Design System (v2)

v2 is pure motion design: there are **no characters, locations or AI footage**, so continuity means one consistent graphic world. Everything below is implemented in `tools/film.html`.

## 1. World and space

- A single dark, deep-green space that behaves like 3-D: panels use `perspective(1800px)` with a gentle rotateY (7° → 3° across each scene) and rotateX 3°; background elements recede by scale, blur and opacity.
- The camera never cuts inside a section. Sections connect by **whip pans** (panels slide ±75% of the frame width with 24 px blur plus 6-sample motion blur) or by the **mint sweep**.
- **Screen direction:** progress moves right → left (RTL). The sweep line travels right → left, the next panel enters from the left, and new rows slide in from the left edge of the list.

## 2. Color

| Role | Value | Rule |
|---|---|---|
| Ink (background base) | `#050C0A` | Acts A–B |
| Deep green | `#0B2A22` / `#14463A` radial | Grows in from the drop (8.0 s) — "clarity" |
| **Mint** | `#41D7B2` | **Reserved for clarity.** It never appears before the drop, except the sonic beeps (sound). After the drop: the sweep, highlights, the key numbers, the CTA |
| Warm white | `#F4F7F5` | Hook amounts |
| Grey noise | `#C4CCC9` + grey haze | Act B only |
| Paper | `#EEEBE4` | Receipts, Act B only |
| Status badges | success `#7DDC9F`, waiting `#F2C66A`, doc `#7FE3C9` | As in the product |

## 3. Typography

| Style | Font | Weight / size (16:9) | Use |
|---|---|---|---|
| Hero numbers | IBM Plex Sans, tabular | 600 / 190 px (scaled per depth) | Act A amounts |
| Hero line | IBM Plex Sans Hebrew | 700 / 180 px | "העסק מכר." |
| Question | IBM Plex Sans Hebrew | 700 / 150 px | "כמה באמת נכנס?" |
| Feature headline | IBM Plex Sans Hebrew | 700 / 84 px, line-height 1.08, tracking −1% | Right third |
| End headline | IBM Plex Sans Hebrew | 700 / 120 px | Center |
| Support | IBM Plex Sans Hebrew | 400 / 30 px, 72% white | Under headlines |
| UI | IBM Plex Sans Hebrew / Plex Sans (money) | As the product, ×1.16 | Panels |

**One text motion only:** the mask reveal (0.55 s expo-out in, 0.28 s quart-in out, 0.08 s line stagger). No typewriter effects except real typing inside the assistant input.

## 4. Motion language

- Arrivals: expo-out (fast in, soft landing). Exits: quart-in. The CTA uses one small overshoot ("back" ease).
- On-beat accents: panels pulse +0.8% scale on every kick (decay 70 ms) from 8.0 to 25.0 s.
- Numbers ease between values over 1.2 s (the product's behavior); tabular figures, so digits don't jitter.
- A slow diagonal sheen crosses every panel (white 7%), about every 5 s.
- Film texture: 6% overlay grain, and motion blur from 6 sub-frames over a 180° shutter.

## 5. Product UI

The product's dark theme rebuilt with the real tokens (`index.css`, `PublicPages.css`) and the real Hebrew strings. Panel: 22 px radius, 1 px `rgba(255,255,255,.1)` border, a deep-green gradient fill, and a large soft shadow. Every panel shows **נתונים להמחשה**.

## 6. Illustrative data (reconciles exactly)

- Before the new sale: gross ₪30,440.00 − VAT ₪4,643.39 − fees ₪639.24 − partial refunds ₪456.13 = **₪24,701.24**
- New sale: שיעור פרטי ₪180.00 (VAT ₪27.46, fee ₪3.78 → net +₪148.76)
- After: gross ₪30,620.00 − VAT ₪4,670.85 − fees ₪643.02 − refunds ₪456.13 = **₪24,850.00** (the website's own preview figures)
- The assistant's answer quotes the same ₪24,850.00.

## 7. Logo

`assets/source/investment-logo.svg`, unaltered, **always on the pale tile** (`#EFF8F5`, radius = 25% of the tile). The lockup is the tile + "מנהל הכנסות" + small-caps "מבית SYDNEY". It is never recolored, animated internally, or placed directly on dark.

## 8. Before / after

| | Noise (0–8 s) | Clarity (8–30 s) |
|---|---|---|
| Color | Black, grey, paper | Deep green + mint |
| Layout | Scattered, overlapping, depth-blurred | Aligned panels, grids |
| Motion | Jitter, drift, rotation | Precise arrivals on the beat |
| Sound | Riser, dissonant clusters | Groove in E major, resolved chords |
