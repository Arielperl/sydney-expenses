# Receiptly Site Redesign — Design Spec

## Problem

The current UI is functional but generic: default Tailwind slate/blue palette, a
font (`Inter`) declared in CSS but never actually loaded (falls back to
system-ui, and doesn't render Hebrew glyphs well anyway), a plain top nav bar,
and no dark mode. The user's explicit feedback: it "looks generic/boring" and
"lacks visual identity." This is a visual-only redesign — no functional or
behavioral changes to any existing feature.

## Goals

- Give the app a distinct visual identity (color, type) instead of default
  Tailwind styling.
- Load a real, Hebrew-capable font consistently across the whole UI.
- Improve layout/comfort: navigation structure, spacing, card style.
- Add a light/dark/system theme toggle, persisted per browser.
- Preserve full RTL (Hebrew) / LTR (English) support — the app already
  switches `dir` via `i18n.dir()`; the redesign must work correctly in both.

## Non-Goals

- No new features, no changes to API contracts, no changes to any page's
  data/behavior logic.
- No new routing structure beyond what's needed to render the new nav.
- No accessibility audit beyond what naturally falls out of using semantic
  color tokens (not a WCAG contrast certification pass).

## Design Tokens

Defined in `frontend/src/index.css` under `@theme`, replacing the current
`brand-*` (blue) and raw `slate-*` usage.

**Brand (primary) — teal**, replacing blue-600:
```
brand-50  #f0fdfa   brand-500 #14b8a6
brand-100 #ccfbf1   brand-600 #0d9488  (primary action color)
brand-200 #99f6e4   brand-700 #0f766e
brand-300 #5eead4   brand-800 #115e59
brand-400 #2dd4bf   brand-900 #134e4a
```

**Neutral — stone**, replacing `slate-*` everywhere (warmer, less clinical):
```
stone-50 #fafaf9 · stone-100 #f5f5f4 · stone-200 #e7e5e4 · stone-300 #d6d3d1
stone-400 #a8a29e · stone-500 #78716c · stone-600 #57534e · stone-700 #44403c
stone-800 #292524 · stone-900 #1c1917 · stone-950 #0c0a09
```

**Accent — amber** (highlights, AI Assistant touches):
```
accent-400 #fbbf24 · accent-500 #f59e0b · accent-600 #d97706
```

**Semantic** (kept distinct from brand teal to avoid hue collision):
- success: green-500 `#22c55e` / green-600 `#16a34a` / green-700 `#15803d`
- danger: red-500 `#ef4444` / red-600 `#dc2626` / red-700 `#b91c1c` (unchanged)

**Surfaces:**
- Light: page bg `stone-50`, card bg `white`, border `stone-200`.
- Dark: page bg `stone-950`, card bg `stone-900`, border `stone-800`, text
  `stone-100` (primary) / `stone-400` (secondary).

**Typography:** Single family across the whole app — **Rubik** (Google
Fonts), weights 400/500/600/700/800. Rubik has full, well-shaped Hebrew
coverage and a matching Latin set, so Hebrew and English render with the same
character instead of Hebrew silently falling back to a system font. Loaded
via a real `<link>` in `index.html` (not the artifact CDN allowlist — this is
the shipped app, not an Artifact). Headings use heavier weights (700/800) for
hierarchy instead of switching families.

**Shape/elevation:** Cards `rounded-2xl`, `shadow-sm` and no border in light
mode; in dark mode replace shadow (invisible on dark bg) with a `stone-800`
border. Buttons `rounded-lg`. Inputs `rounded-lg` with a `brand-500` focus
ring.

## Layout

Replace the current single top nav bar with:
- **Desktop (≥ lg):** fixed sidebar (RTL: right-hand side, following the
  document's `dir`), ~240px wide, containing the logo, nav items (using
  `lucide-react`, already a dependency, for icons), and the language switcher
  + new theme switcher pinned at the bottom.
- **Mobile/tablet (< lg):** a slim top app bar with a hamburger button that
  opens a slide-in drawer with the same nav content, plus a backdrop —
  structurally the same interaction pattern as the existing `Modal`
  component (Escape to close, click-outside to close).

This is the single biggest structural change and directly answers "generic /
no identity": a plain horizontal link list reads as a content page, a
sidebar reads as a real business application.

## Dark Mode

- Tailwind v4 class-based dark variant: add
  `@custom-variant dark (&:where(.dark, .dark *));` to `index.css`, and use
  `dark:` utilities throughout components.
- A `ThemeProvider` (React context) manages three states — `light`, `dark`,
  `system` — stored under `localStorage["receiptly-theme"]`. `system` follows
  `prefers-color-scheme` and stays live via a `matchMedia` change listener.
  The resolved theme (`light`/`dark`) is applied as a `dark` class on
  `document.documentElement`.
- A `ThemeSwitcher` component, styled and interacting like the existing
  `LanguageSwitcher` (a button that opens a small dropdown with 3 options),
  placed next to it in the sidebar/drawer.
- `recharts` (used by `CategoryChart`) renders its own SVG and does not see
  Tailwind's `dark:` classes. `CategoryChart` will read the resolved theme
  from the new theme context and switch its hardcoded grid/tick/tooltip hex
  colors (currently `#e2e8f0`, `#64748b`, `#334155`, `#f1f5f9`) between a
  light and dark set. The categorical bar colors (`categoryColors.ts`) stay
  as-is — they're already mid-saturation and read fine on both backgrounds.

## Components Affected

Every existing page (`DashboardPage`, `ExpensesPage`, `AddExpensePage`,
`UploadReceiptPage`, `AssistantPage`) and shared component (`Layout` →
replaced by `Sidebar`/`AppShell`, `StatCard`, `CategoryChart`, `CategoryBadge`,
`ExtractionModeBadge`, `FormField`, `ExpenseForm`, `ExpenseList`, `Modal`,
`ReceiptDropzone`, `ReceiptImage`, `StatusStates`, `LanguageSwitcher` +new
`ThemeSwitcher`) gets its color classes (`slate-*` → `stone-*`, `brand-*`
values, hardcoded hex in charts) and shape classes (`rounded-xl` →
`rounded-2xl` where it's a card) updated, plus `dark:` variants added. No
component's props, behavior, or test-observable output (text content, roles,
data) changes — only class names and the two new files (`ThemeProvider`,
`ThemeSwitcher`) and the sidebar layout change what's rendered structurally
around `<Outlet />`.

## Testing

- Existing component tests assert on text/roles/behavior, not on Tailwind
  classes, so they should continue to pass unchanged for pages that only get
  restyled.
- `Layout`'s replacement (sidebar/drawer) changes DOM structure, so its
  existing test (if any) and any test that queries nav landmarks needs
  re-verification.
- New tests: `ThemeProvider`/`ThemeSwitcher` (persists choice, applies `dark`
  class, respects `system` + `matchMedia` changes) and drawer open/close
  behavior on mobile.
- Manual verification in the browser preview: both themes × both languages
  (4 combinations) on at least Dashboard and one form page, plus a mobile
  viewport check of the drawer.

## Rollout

Single redesign pass across the existing branch (`main`, per this project's
established working pattern) — not a feature-flagged gradual rollout. Land as
one cohesive change since it's a pure style/layout pass with no data risk.
