# Project Analysis — מנהל הכנסות מבית Sydney

Status: inspection complete · 2026-09-24
Rule used throughout: **C** = confirmed in project files · **A** = creative assumption · **M** = missing, needs confirmation.

---

## 1. Business name

| Item | Value | Source |
|---|---|---|
| Customer-facing product name | **מנהל הכנסות מבית Sydney** ("Revenue Manager by Sydney") **C** | `README.md` L3–5, `frontend/index.html` `<title>` |
| Brand lockup on site | "מנהל הכנסות" + small caps "מבית SYDNEY" **C** | `frontend/src/pages/HomePage.tsx` `PublicBrand` |
| Names to avoid on screen | "sydney-expenses", "Receiptly", "Sydney Transaction Management" — legacy internal names **C** | `README.md` L5, `docs/superpowers/specs/2026-09-09-site-redesign-design.md` |

## 2. Business summary (C)

A web app for **Israeli small businesses** that gathers every sale in one place — automatically from the payment provider (Grow, Cardcom), from a CSV export, or entered by hand — and turns it into a clear picture of what came in. It tracks whether each sale has its customer document (receipt/invoice), surfaces only the sales that genuinely need action, and has an AI assistant that answers questions about the business's own sales data.

The site's own core promise (hero, `HomePage.tsx`, updated 2026-09-25):
> Eyebrow **מנהל הכנסות לעסקים** · headline **מכירות, הכנסות ומה שדורש טיפול. במקום אחד.** — "Sales, revenue and what needs attention. In one place."
> Supporting text: **מרכזים עסקאות ממקורות מחוברים, עוקבים אחרי הנתונים הכספיים ורואים אילו מכירות צריכות פעולה.**

## 3. Product / service (C unless marked)

| Capability | What the owner experiences | Source |
|---|---|---|
| Automatic sale capture | A customer pays through Grow or Cardcom → the sale appears on its own, no typing | `README.md` "Automatic sale ingestion", `HomePage.tsx` connections section |
| CSV import | Upload a sales export from any other source, preview, confirm | `README.md` "CSV import format" |
| Manual sale entry | Fallback when no provider is connected | `README.md` L83 |
| Dashboard ("לוח בקרה") | Gross revenue, VAT included, processing fees, partial refunds → **net receipts after deductions**, with an explanation of how each number is derived; revenue trend chart; top services | `DashboardPage.tsx`, `he/translation.json` `dashboard.*` |
| "דורש טיפול" (Needs attention) | One short, deduplicated list of sales that need an action — missing document, document that never arrived, VAT treatment to review. Healthy sales never clutter it | `README.md` "Refunds and the Exception Center", `exceptions.*` strings |
| Provider documents | Grow/Cardcom documents linked to the sale automatically when the provider sends them | `README.md` "Automatic provider documents" |
| AI assistant ("עוזר AI") | Ask in plain Hebrew: "כמה הכנסתי החודש?", "איזה שירות נמכר הכי הרבה?" — answers only from the business's own data; distinguishes gross / net / profit | `README.md` "AI Assistant", `assistant.exampleQuestion*` |
| Israeli VAT (18%), ILS, Hebrew-first RTL | Built for Israel | `README.md` "Israeli VAT and currency", `index.html lang="he"` |
| Private per-business workspace | Each business sees only its own data | `README.md` "Public website and authentication", `docs/business-isolation.md` |

## 4. Target audience

- **C:** Israeli small businesses ("נבנה לעסקים קטנים") that collect card payments — the site names Grow and Cardcom, both popular with Israeli small service businesses.
- **C:** Hebrew-speaking owners; public site is Hebrew-only.
- **A:** The sample data (`backend/samples/sales-sample.csv`: consulting session, web design package, monthly subscription) suggests **service businesses and solo professionals** — studio owners, therapists, consultants, freelancers — who are also their own bookkeeper at the end of the day.
- **A:** Emotional profile: busy, competent, hands-on owners who sell all day and only face the numbers late at night; not accountants and not "finance people."

## 5. Main customer problem

- **C (implied by copy):** Sales scattered across payment systems and reports; manual re-entry; not knowing what actually came in versus what was charged; missing receipts discovered too late. Site: "פחות מעבר בין דוחות ומערכות", "פחות עבודה ידנית", "פחות סימני שאלה", "יודעים מה דורש טיפול".
- **A (emotional cost):** the owner ends the day unsure — the till "said" one number, the bank shows another, and somewhere there are sales without documents. The cost is mental: the business is never fully "closed" in their head.

## 6. Primary solution (C)

Connect once → every sale flows in by itself → one honest picture of what came in, plus a short list of the few things that need you.
Site: "שלושה צעדים, פעם אחת. מכאן והלאה כל מכירה נקלטת ומסתדרת במקום שלה."

## 7. Main benefit

**Clarity without the manual work** — knowing what came in, what changed and what's next, without chasing it. (Hero sub-copy: "כדי שתדעו מה נכנס, מה השתנה ומה הצעד הבא.")

## 8. Differentiators (C)

1. **Honest numbers.** Net receipts are labelled as *not* profit and *not* a bank balance; every figure explains how it was derived. Different currencies are never summed. (`README.md` "Interface design system → Financial wording")
2. **Only what needs you.** The attention list excludes healthy sales and already-handled refunds — "without overloading correct transactions."
3. **Direct Grow and Cardcom connections** + CSV for everything else.
4. **Hebrew-first, Israeli VAT built in.**
5. **An assistant that answers from your own data** and never invents a figure.

## 9. Brand personality (C from copy + design system; wording A)

Calm, precise, understated, honest, warm-competent. Short declarative Hebrew sentences in pairs ("המידע מגיע. אתם ממשיכים לעבוד."). No hype, no growth promises — the site's product preview is explicitly labelled "נתונים להמחשה" (illustrative data). The brand's tagline-like line: **"נבנה לעסקים קטנים. חושב על הפרטים הגדולים."**

## 10. Existing visual identity (C)

| Element | Value | Source |
|---|---|---|
| Primary teal-green | `brand-600 #17745F`, `brand-400 #47B395`, `brand-300 #7CCDB5` | `frontend/src/index.css` |
| Signature mint (dark surfaces only) | `#41D7B2` | `PublicPages.css` |
| Deep green-black | `#0B2A22` → `#071A15`, radial `#14463A` | `PublicPages.css` `.public-hero` |
| Green-tinted neutrals | `zinc-50 #F6F7F6` … `zinc-900 #151A19` | `index.css` |
| Warm accent (sparingly) | `accent-400 #F2B544` | `index.css` |
| Typeface | **IBM Plex Sans Hebrew** + IBM Plex Sans (400/500/600/700) | `index.html`, `index.css` |
| Money style | tabular figures, medium weight (not bold), `₪` with `<bdi>` isolation | `README.md`, `Money.tsx` |
| Motion | short ease-out-quart entrances (≈260 ms), one-shot reveals, numbers ease between values, reduced-motion respected | `index.css`, `README.md` "Motion" |
| Hero image | Dark green-black field with glowing mint wave and translucent data panels | `frontend/public/images/sydney-hero-clean.png` |
| Logo | Navy `#082D62` bar chart + green `#02A94E` rising arrow; shown inside a pale `brand-50` rounded tile | `frontend/src/assets/investment-logo.svg`, `.public-brand-mark` |

**Observation (A):** the logo's navy/green does not match the teal system and vanishes on dark backgrounds. The film must always present it on the pale rounded tile, exactly as the website does, and never recolour it.

## 11. Available assets

| Asset | Usable? | Copied to |
|---|---|---|
| `investment-logo.svg` (vector) | Yes — on light tile only | `assets/source/investment-logo.svg` (+ `logo-render-600.png` preview) |
| `sydney-hero-clean.png` 1672×941 | Yes — as brand texture / end-card background | `assets/source/sydney-hero-clean.png` |
| `sydney-hero.png` 2048×1152 | **No** — contains garbled AI-generated pseudo-Hebrew text | not copied |
| Real product UI (live app) | Yes, via screen capture of the running app with a demo/fictional workspace | to be captured |
| Illustrative dashboard figures (₪30,620.00 gross → ₪24,850.00 net, reconciles exactly) | Yes — already publicly used and labelled illustrative | `HomePage.tsx` `PREVIEW_ROWS` |
| Video, music, sound effects, photography of people | **None exist** | — |
| Testimonials, case studies, customer logos, statistics | **None exist** | — |

## 12. Existing calls to action (C)

- Primary: **"פתיחת חשבון"** (Open an account) → `/signup`
- Hero: "מתחילים לנהל הכנסות" (Start managing revenue)
- Secondary: "לראות איך זה עובד"
- Closing section: eyebrow "פחות סימני שאלה" / headline "הצעד הבא של העסק מתחיל בתמונה ברורה." / button "פתיחת חשבון"

## 13. Confirmed claims the film may use

- Sales from Grow and Cardcom are captured automatically once connected; CSV imports from any other source; manual entry possible.
- One place for sales, receipts (תקבולים) and exceptions.
- The dashboard shows gross, VAT, processing fees, partial refunds and net receipts, and explains each.
- A clear list of what needs attention; healthy sales stay out of it.
- An AI assistant answers questions about the business's own sales (example questions from the product).
- Hebrew, Israeli VAT.

## 14. Restrictions — claims the film must NOT make

- ❌ No profit claims. Net receipts **are not profit and not a bank balance** (product states this explicitly).
- ❌ No "replaces your accountant" — FAQ explicitly says it does not.
- ❌ No claim that Sydney **issues** tax invoices/receipts — it tracks and links provider documents; its own issuance is not implemented.
- ❌ No refund ingestion from providers, no bank connection, no expense tracking.
- ❌ No statistics, time-saved figures, customer counts, awards, testimonials, prices, free trials or guarantees — none exist.
- ❌ No Grow/Cardcom **logos** (trademarks; names in plain text only, as on the website).
- ❌ Any numbers shown are illustrative and must be labelled as such (the website does this: "נתונים להמחשה").
- ❌ Product is in a rollout/pilot stage ("המוצר נמצא בשלב ההרצה" — FAQ); avoid "join thousands of businesses" style framing.

## 15. Missing information (M)

1. Public website domain for the end card (only the API host `sydney-revenue-api.vercel.app` appears in the repo).
2. Target platforms and paid-media plans.
3. Production route and budget (AI video, practical shoot, or motion-graphics only).
4. Whether a specific industry should be the hero (studio, clinic, consultant…).
5. Pricing (none in project — film will not mention price).

## 16. Creative assumptions (A)

- Language: Hebrew on-screen copy, RTL.
- Primary audience: solo owners / small service businesses taking card payments.
- Tone: calm and precise — matching the site. No trailer drama.
- Hero business: a small pilates/movement studio owner (credible Grow/Cardcom user, visual, human, repeatable sale moments). Replaceable without changing the structure.

## 17. Relevant source files

- `README.md` (product truth, claims boundaries, design system)
- `frontend/src/pages/HomePage.tsx` (all marketing copy, CTAs, FAQ, illustrative figures)
- `frontend/src/pages/PublicPages.css`, `frontend/src/index.css` (colour, type, motion tokens)
- `frontend/index.html` (fonts, meta description, theme colour)
- `frontend/src/i18n/locales/he/translation.json` (exact in-app Hebrew UI vocabulary)
- `frontend/src/assets/investment-logo.svg`, `frontend/public/images/sydney-hero-clean.png`
- `backend/samples/sales-sample.csv` (audience hint)
- `docs/business-isolation.md`, `docs/security.md` (privacy/isolation claims)
