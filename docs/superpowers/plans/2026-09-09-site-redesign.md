# Site Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Receiptly a distinct visual identity (teal/stone/amber palette, Rubik
typeface, sidebar navigation) and a persisted light/dark/system theme toggle,
with zero change to any existing feature's behavior.

**Architecture:** All color/shape changes flow through Tailwind v4 `@theme`
tokens in `index.css` so most components need no edits at all. A new
`ThemeProvider` (React context) resolves `light`/`dark`/`system` to a
`resolvedTheme` and toggles a `dark` class on `<html>`; Tailwind's `dark:`
variant (enabled via `@custom-variant dark`) then drives per-component dark
styling. The existing top nav bar is replaced by a responsive
sidebar (desktop) / slide-in drawer (mobile), reusing the `Modal`
component's backdrop+Escape interaction pattern.

**Tech Stack:** Tailwind CSS v4 (already installed), `lucide-react` (already
installed, used for nav/theme icons), Google Fonts (Rubik, loaded via a
`<link>` in `index.html` — this is the shipped app, not an Artifact, so the
CDN allowlist that applies to Artifacts doesn't apply here).

## Global Constraints

- No new npm dependencies — everything needed (`lucide-react`, Tailwind v4)
  is already installed.
- No changes to any API contract, route path, component prop, or
  test-observable text/role/behavior — this is a visual-only pass per the
  design spec's Non-Goals.
- RTL (Hebrew) and LTR (English) must both keep working — use logical
  properties (`ps-*`/`pe-*`/`start-*`/`end-*`/`border-s`/`border-e`) instead of
  physical `left`/`right` wherever a new left/right-sensitive layout is added
  (the sidebar and drawer).
- Every task ends with a commit, per this repo's established workflow.

---

### Task 1: Design tokens and font

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Produces: the `brand-*` (teal), `success-*` (green), `danger-*` (red, value
  unchanged), and new `accent-*` (amber) color tokens; the `--font-sans`
  token now resolves to Rubik; a `dark:` variant is now enabled and usable by
  every later task via `@custom-variant dark (&:where(.dark, .dark *));`.

There's no new application logic in this task — it's CSS tokens and a
`<link>` tag — so verification is "the app still builds and the fonts load,"
not a unit test. Visual confirmation happens in Task 7's live browser check.

- [ ] **Step 1: Add the Rubik font link to `index.html`**

Replace the `<head>` of `frontend/index.html` with:

```html
<!doctype html>
<html lang="he" dir="rtl">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;600;700;800&display=swap"
      rel="stylesheet"
    />
    <title>Receiptly</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2: Replace the theme tokens in `frontend/src/index.css`**

```css
@import "tailwindcss";

@custom-variant dark (&:where(.dark, .dark *));

@theme {
  --color-brand-50: #f0fdfa;
  --color-brand-100: #ccfbf1;
  --color-brand-200: #99f6e4;
  --color-brand-300: #5eead4;
  --color-brand-400: #2dd4bf;
  --color-brand-500: #14b8a6;
  --color-brand-600: #0d9488;
  --color-brand-700: #0f766e;
  --color-brand-800: #115e59;
  --color-brand-900: #134e4a;

  --color-success-50: #f0fdf4;
  --color-success-500: #22c55e;
  --color-success-600: #16a34a;
  --color-success-700: #15803d;

  --color-danger-50: #fef2f2;
  --color-danger-500: #ef4444;
  --color-danger-600: #dc2626;
  --color-danger-700: #b91c1c;

  --color-accent-400: #fbbf24;
  --color-accent-500: #f59e0b;
  --color-accent-600: #d97706;

  --font-sans: "Rubik", ui-sans-serif, system-ui, -apple-system, sans-serif;
}

html,
body,
#root {
  height: 100%;
}

body {
  background-color: #fafaf9;
  color: #1c1917;
}

.dark body {
  background-color: #0c0a09;
  color: #f5f5f4;
}

* {
  -webkit-tap-highlight-color: transparent;
}
```

- [ ] **Step 3: Verify the build still compiles**

Run: `npm run build`
Expected: build succeeds with no Tailwind/PostCSS errors (the previous
`brand-*`/`success-*`/`danger-*` token names are unchanged, only their hex
values and the new `accent-*`/`@custom-variant` are added, so every existing
class reference stays valid).

- [ ] **Step 4: Commit**

```bash
git add frontend/index.html frontend/src/index.css
git commit -m "Add teal/stone/amber theme tokens, Rubik font, and dark-mode variant"
```

---

### Task 2: Theme system (ThemeProvider + ThemeSwitcher)

**Files:**
- Modify: `frontend/src/test/setup.ts` (add a default `matchMedia` shim —
  jsdom doesn't implement it, and every test that renders `ThemeProvider`
  needs it to exist)
- Modify: `frontend/src/test/test-utils.tsx` (wrap `renderWithProviders` in
  `ThemeProvider`, matching how `main.tsx` will compose providers)
- Create: `frontend/src/contexts/ThemeContext.tsx`
- Test: `frontend/src/contexts/__tests__/ThemeContext.test.tsx`
- Create: `frontend/src/components/ThemeSwitcher.tsx`
- Test: `frontend/src/components/__tests__/ThemeSwitcher.test.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/i18n/locales/he/translation.json`
- Modify: `frontend/src/i18n/locales/en/translation.json`

**Interfaces:**
- Produces: `ThemeProvider` (React component), `useTheme(): { mode:
  ThemeMode; resolvedTheme: ResolvedTheme; setMode: (mode: ThemeMode) => void
  }`, and the `ThemeMode` (`'light' | 'dark' | 'system'`) /
  `ResolvedTheme` (`'light' | 'dark'`) types — Task 3 and Task 4 both import
  `useTheme` and `ResolvedTheme` from `../contexts/ThemeContext`.
- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Add a default `matchMedia` shim to the test setup**

`frontend/src/test/setup.ts` currently has no `matchMedia` polyfill; jsdom
doesn't provide one, and `ThemeProvider` calls
`window.matchMedia('(prefers-color-scheme: dark)')` on every render. Add the
shim near the top, before the existing MSW setup:

```ts
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, beforeEach } from 'vitest'

import i18n, { DEFAULT_LANGUAGE, LANGUAGE_STORAGE_KEY } from '../i18n'
import { server } from './msw/server'

if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia
}

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

beforeEach(() => {
  window.localStorage.clear()
  if (i18n.language !== DEFAULT_LANGUAGE) {
    void i18n.changeLanguage(DEFAULT_LANGUAGE)
  }
})

afterEach(() => {
  cleanup()
  window.localStorage.removeItem(LANGUAGE_STORAGE_KEY)
})
```

(Individual tests that need to simulate a specific OS preference — like
`ThemeContext.test.tsx` — override `window.matchMedia` with their own `vi.fn()`
mock; this shim is only the safe default for every other test.)

- [ ] **Step 2: Write the failing `ThemeContext` test**

Create `frontend/src/contexts/__tests__/ThemeContext.test.tsx`:

```tsx
import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ThemeProvider, useTheme } from '../ThemeContext'

function mockMatchMedia(matches: boolean) {
  const listeners = new Set<() => void>()
  const mediaQueryList = {
    matches,
    media: '(prefers-color-scheme: dark)',
    addEventListener: (_event: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_event: string, listener: () => void) => listeners.delete(listener),
  }
  window.matchMedia = vi.fn().mockReturnValue(mediaQueryList) as unknown as typeof window.matchMedia
  return {
    fireChange: (newMatches: boolean) => {
      mediaQueryList.matches = newMatches
      listeners.forEach((listener) => listener())
    },
  }
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.classList.remove('dark')
  })

  afterEach(() => {
    document.documentElement.classList.remove('dark')
  })

  it('defaults to system mode and resolves to the OS preference', () => {
    mockMatchMedia(true)
    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider })
    expect(result.current.mode).toBe('system')
    expect(result.current.resolvedTheme).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('reads a previously stored mode from localStorage', () => {
    mockMatchMedia(false)
    window.localStorage.setItem('receiptly-theme', 'dark')
    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider })
    expect(result.current.mode).toBe('dark')
    expect(result.current.resolvedTheme).toBe('dark')
  })

  it('setMode persists the choice and updates the document class', () => {
    mockMatchMedia(false)
    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider })

    act(() => result.current.setMode('dark'))
    expect(window.localStorage.getItem('receiptly-theme')).toBe('dark')
    expect(result.current.resolvedTheme).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)

    act(() => result.current.setMode('light'))
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('tracks OS preference changes while in system mode', () => {
    const media = mockMatchMedia(false)
    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider })
    expect(result.current.resolvedTheme).toBe('light')

    act(() => media.fireChange(true))
    expect(result.current.resolvedTheme).toBe('dark')
  })
})
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `npx vitest run src/contexts/__tests__/ThemeContext.test.tsx`
Expected: FAIL — `Cannot find module '../ThemeContext'`

- [ ] **Step 4: Implement `ThemeContext`**

Create `frontend/src/contexts/ThemeContext.tsx`:

```tsx
import type { ReactNode } from 'react'
import { createContext, useContext, useEffect, useState } from 'react'

export type ThemeMode = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

interface ThemeContextValue {
  mode: ThemeMode
  resolvedTheme: ResolvedTheme
  setMode: (mode: ThemeMode) => void
}

const THEME_STORAGE_KEY = 'receiptly-theme'
const DARK_MEDIA_QUERY = '(prefers-color-scheme: dark)'

function isThemeMode(value: string | null): value is ThemeMode {
  return value === 'light' || value === 'dark' || value === 'system'
}

function getSystemTheme(): ResolvedTheme {
  return window.matchMedia(DARK_MEDIA_QUERY).matches ? 'dark' : 'light'
}

function resolveTheme(mode: ThemeMode): ResolvedTheme {
  return mode === 'system' ? getSystemTheme() : mode
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(() => {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY)
    return isThemeMode(stored) ? stored : 'system'
  })
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() => resolveTheme(mode))

  useEffect(() => {
    setResolvedTheme(resolveTheme(mode))
    if (mode !== 'system') return

    const media = window.matchMedia(DARK_MEDIA_QUERY)
    const handleChange = () => setResolvedTheme(getSystemTheme())
    media.addEventListener('change', handleChange)
    return () => media.removeEventListener('change', handleChange)
  }, [mode])

  useEffect(() => {
    document.documentElement.classList.toggle('dark', resolvedTheme === 'dark')
  }, [resolvedTheme])

  function setMode(newMode: ThemeMode) {
    window.localStorage.setItem(THEME_STORAGE_KEY, newMode)
    setModeState(newMode)
  }

  return <ThemeContext.Provider value={{ mode, resolvedTheme, setMode }}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext)
  if (!context) throw new Error('useTheme must be used within a ThemeProvider')
  return context
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `npx vitest run src/contexts/__tests__/ThemeContext.test.tsx`
Expected: PASS (4/4)

- [ ] **Step 6: Add theme translation keys**

In `frontend/src/i18n/locales/he/translation.json`, add a `theme` section
right after the existing `language` section:

```json
  "language": {
    "switcherLabel": "שפה",
    "changeLanguage": "שינוי שפה",
    "hebrew": "עברית",
    "english": "אנגלית"
  },
  "theme": {
    "switcherLabel": "מצב תצוגה",
    "changeTheme": "שינוי מצב תצוגה",
    "light": "בהיר",
    "dark": "כהה",
    "system": "לפי המערכת"
  },
```

In `frontend/src/i18n/locales/en/translation.json`, add the matching section
after `language`:

```json
  "language": {
    "switcherLabel": "Language",
    "changeLanguage": "Change language",
    "hebrew": "Hebrew",
    "english": "English"
  },
  "theme": {
    "switcherLabel": "Theme",
    "changeTheme": "Change theme",
    "light": "Light",
    "dark": "Dark",
    "system": "System"
  },
```

- [ ] **Step 7: Write the failing `ThemeSwitcher` test**

Create `frontend/src/components/__tests__/ThemeSwitcher.test.tsx`:

```tsx
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ThemeSwitcher } from '../ThemeSwitcher'
import { ThemeProvider } from '../../contexts/ThemeContext'
import { render, screen } from '../../test/test-utils'

function renderSwitcher() {
  return render(
    <ThemeProvider>
      <ThemeSwitcher />
    </ThemeProvider>,
  )
}

describe('ThemeSwitcher', () => {
  it('opens a menu with all three theme options', async () => {
    const user = userEvent.setup()
    renderSwitcher()
    await user.click(screen.getByRole('button', { name: 'שינוי מצב תצוגה' }))

    expect(screen.getByRole('option', { name: /בהיר/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /כהה/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /לפי המערכת/ })).toBeInTheDocument()
  })

  it('selecting dark mode applies the dark class to the document', async () => {
    const user = userEvent.setup()
    renderSwitcher()
    await user.click(screen.getByRole('button', { name: 'שינוי מצב תצוגה' }))
    await user.click(screen.getByTestId('theme-option-dark'))

    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })
})
```

- [ ] **Step 8: Run the test to verify it fails**

Run: `npx vitest run src/components/__tests__/ThemeSwitcher.test.tsx`
Expected: FAIL — `Cannot find module '../ThemeSwitcher'`

- [ ] **Step 9: Implement `ThemeSwitcher`**

Create `frontend/src/components/ThemeSwitcher.tsx`, mirroring the existing
`LanguageSwitcher` dropdown pattern exactly (same open/close-on-outside-click,
Escape-to-close, and roving-arrow-free simple list, so the two switchers
behave identically):

```tsx
import { Check, Monitor, Moon, Sun } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useTheme, type ThemeMode } from '../contexts/ThemeContext'

const MODE_ICON: Record<ThemeMode, typeof Sun> = {
  light: Sun,
  dark: Moon,
  system: Monitor,
}

const MODES: ThemeMode[] = ['light', 'dark', 'system']

export function ThemeSwitcher() {
  const { t } = useTranslation()
  const { mode, setMode } = useTheme()
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!isOpen) return

    function handlePointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsOpen(false)
        triggerRef.current?.focus()
      }
    }
    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen])

  const CurrentIcon = MODE_ICON[mode]

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-label={t('theme.changeTheme')}
        title={t('theme.changeTheme')}
        className="flex h-9 w-9 items-center justify-center rounded-md border border-stone-300 bg-white text-stone-600 shadow-sm transition-colors hover:bg-stone-100 hover:text-stone-900 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-300 dark:hover:bg-stone-800 dark:hover:text-stone-100"
      >
        <CurrentIcon className="h-4 w-4" aria-hidden="true" />
      </button>

      {isOpen && (
        <div
          role="listbox"
          aria-label={t('theme.switcherLabel')}
          className="absolute end-0 z-20 mt-2 w-40 overflow-hidden rounded-md border border-stone-200 bg-white py-1 shadow-lg dark:border-stone-700 dark:bg-stone-900"
        >
          {MODES.map((option) => {
            const isSelected = mode === option
            const Icon = MODE_ICON[option]
            return (
              <button
                key={option}
                type="button"
                role="option"
                aria-selected={isSelected}
                data-testid={`theme-option-${option}`}
                onClick={() => {
                  setMode(option)
                  setIsOpen(false)
                  triggerRef.current?.focus()
                }}
                className={[
                  'flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors focus:outline-none focus:bg-stone-100 dark:focus:bg-stone-800',
                  isSelected
                    ? 'font-medium text-brand-700 dark:text-brand-400'
                    : 'text-stone-700 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800',
                ].join(' ')}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                <span className="flex-1 text-start">{t(`theme.${option}`)}</span>
                {isSelected && <Check className="h-4 w-4 text-brand-600 dark:text-brand-400" aria-hidden="true" />}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 10: Run the test to verify it passes**

Run: `npx vitest run src/components/__tests__/ThemeSwitcher.test.tsx`
Expected: PASS (2/2)

- [ ] **Step 11: Wrap `renderWithProviders` in `ThemeProvider`**

`CategoryChart` (Task 4) and `Layout` (Task 3) will both call `useTheme()`,
so any page test that renders them needs a `ThemeProvider` in the tree.
Update `frontend/src/test/test-utils.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'

import { ThemeProvider } from '../contexts/ThemeContext'

export function renderWithProviders(
  ui: ReactElement,
  { route = '/' }: { route?: string } = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
        </QueryClientProvider>
      </ThemeProvider>
    )
  }

  return render(ui, { wrapper: Wrapper })
}

export * from '@testing-library/react'
```

- [ ] **Step 12: Wire `ThemeProvider` into `main.tsx`**

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App.tsx'
import { ThemeProvider } from './contexts/ThemeContext'
import './i18n'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
)
```

- [ ] **Step 13: Run the full frontend suite to confirm no regressions**

Run: `npm run lint && npx tsc -b && npm test`
Expected: all pass (the `test-utils.tsx` change adds a provider around every
existing `renderWithProviders` call; since no existing component reads theme
context, this should be a no-op for all of them).

- [ ] **Step 14: Commit**

```bash
git add frontend/src/test/setup.ts frontend/src/test/test-utils.tsx \
  frontend/src/contexts/ThemeContext.tsx frontend/src/contexts/__tests__/ThemeContext.test.tsx \
  frontend/src/components/ThemeSwitcher.tsx frontend/src/components/__tests__/ThemeSwitcher.test.tsx \
  frontend/src/main.tsx frontend/src/i18n/locales/he/translation.json frontend/src/i18n/locales/en/translation.json
git commit -m "Add light/dark/system theme provider and switcher"
```

---

### Task 3: Sidebar navigation (desktop) + slide-in drawer (mobile)

**Files:**
- Modify: `frontend/src/components/Layout.tsx`
- Test: `frontend/src/components/__tests__/Layout.test.tsx`
- Modify: `frontend/src/i18n/locales/he/translation.json`
- Modify: `frontend/src/i18n/locales/en/translation.json`

**Interfaces:**
- Consumes: `ThemeSwitcher` and `useTheme`/`ThemeProvider` from Task 2.
- Produces: `Layout` (unchanged export name and unchanged usage — still just
  `<Route element={<Layout />}>` wrapping `<Outlet />` in `App.tsx`, so
  `App.tsx` needs no edits).

No existing test renders `Layout` (every page test calls `renderWithProviders(<SomePage />)`
directly, bypassing `Layout` entirely), so this task's test is new, not a
modification of an existing one.

- [ ] **Step 1: Add nav-menu translation keys**

In `frontend/src/i18n/locales/he/translation.json`, add to the existing
`nav` section:

```json
  "nav": {
    "dashboard": "לוח בקרה",
    "expenses": "הוצאות",
    "addExpense": "הוספת הוצאה",
    "uploadReceipt": "העלאת קבלה",
    "assistant": "עוזר AI",
    "mainNavigation": "ניווט ראשי",
    "openMenu": "פתיחת תפריט"
  },
```

In `frontend/src/i18n/locales/en/translation.json`:

```json
  "nav": {
    "dashboard": "Dashboard",
    "expenses": "Expenses",
    "addExpense": "Add expense",
    "uploadReceipt": "Upload receipt",
    "assistant": "AI Assistant",
    "mainNavigation": "Main navigation",
    "openMenu": "Open menu"
  },
```

- [ ] **Step 2: Write the failing `Layout` test**

Create `frontend/src/components/__tests__/Layout.test.tsx`:

```tsx
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { Layout } from '../Layout'
import { ThemeProvider } from '../../contexts/ThemeContext'
import { render, screen } from '../../test/test-utils'

function renderLayout() {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<div>Dashboard content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  )
}

describe('Layout', () => {
  it('renders all nav links and the routed page content', () => {
    renderLayout()
    expect(screen.getByRole('link', { name: /לוח בקרה/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /עוזר AI/ })).toBeInTheDocument()
    expect(screen.getByText('Dashboard content')).toBeInTheDocument()
  })

  it('opens the mobile drawer and closes it on Escape', async () => {
    const user = userEvent.setup()
    renderLayout()

    expect(screen.getAllByRole('link', { name: /הוצאות/ })).toHaveLength(1)

    await user.click(screen.getByRole('button', { name: 'פתיחת תפריט' }))
    expect(screen.getAllByRole('link', { name: /הוצאות/ })).toHaveLength(2)

    await user.keyboard('{Escape}')
    expect(screen.getAllByRole('link', { name: /הוצאות/ })).toHaveLength(1)
  })
})
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `npx vitest run src/components/__tests__/Layout.test.tsx`
Expected: FAIL (the current `Layout` renders a single top bar with no
hamburger button, so `getByRole('button', { name: 'פתיחת תפריט' })` finds
nothing)

- [ ] **Step 4: Implement the sidebar + drawer `Layout`**

Replace `frontend/src/components/Layout.tsx`:

```tsx
import { Bot, LayoutDashboard, Menu, PlusCircle, Receipt, Upload, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet } from 'react-router-dom'

import { LanguageSwitcher } from './LanguageSwitcher'
import { ThemeSwitcher } from './ThemeSwitcher'

const NAV_ITEMS = [
  { to: '/', key: 'dashboard', end: true, icon: LayoutDashboard },
  { to: '/expenses', key: 'expenses', end: false, icon: Receipt },
  { to: '/add-expense', key: 'addExpense', end: false, icon: PlusCircle },
  { to: '/upload-receipt', key: 'uploadReceipt', end: false, icon: Upload },
  { to: '/assistant', key: 'assistant', end: false, icon: Bot },
] as const

function navLinkClasses(isActive: boolean): string {
  return [
    'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
    isActive
      ? 'bg-brand-600 text-white'
      : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900 dark:text-stone-400 dark:hover:bg-stone-800 dark:hover:text-stone-100',
  ].join(' ')
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useTranslation()
  return (
    <nav aria-label={t('nav.mainNavigation')} className="flex flex-1 flex-col gap-1">
      {NAV_ITEMS.map((item) => (
        <NavLink key={item.to} to={item.to} end={item.end} onClick={onNavigate} className={({ isActive }) => navLinkClasses(isActive)}>
          <item.icon className="h-5 w-5" aria-hidden="true" />
          {t(`nav.${item.key}`)}
        </NavLink>
      ))}
    </nav>
  )
}

function BrandMark() {
  return (
    <div className="flex items-center gap-2 px-2">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
        R
      </span>
      <span className="text-lg font-semibold text-stone-900 dark:text-stone-100">Receiptly</span>
    </div>
  )
}

export function Layout() {
  const { t } = useTranslation()
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)

  useEffect(() => {
    if (!isDrawerOpen) return
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setIsDrawerOpen(false)
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isDrawerOpen])

  return (
    <div className="min-h-full lg:flex">
      <aside className="hidden w-60 flex-col border-e border-stone-200 bg-white px-4 py-6 lg:flex dark:border-stone-800 dark:bg-stone-900">
        <BrandMark />
        <div className="mt-8 flex flex-1 flex-col">
          <NavLinks />
        </div>
        <div className="flex items-center gap-2">
          <LanguageSwitcher />
          <ThemeSwitcher />
        </div>
      </aside>

      <div className="flex-1">
        <header className="flex items-center justify-between border-b border-stone-200 bg-white px-4 py-3 lg:hidden dark:border-stone-800 dark:bg-stone-900">
          <BrandMark />
          <button
            type="button"
            onClick={() => setIsDrawerOpen(true)}
            aria-label={t('nav.openMenu')}
            className="flex h-9 w-9 items-center justify-center rounded-md border border-stone-300 text-stone-600 hover:bg-stone-100 dark:border-stone-700 dark:text-stone-300 dark:hover:bg-stone-800"
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
          </button>
        </header>

        {isDrawerOpen && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <button
              aria-label={t('common.closeDialog')}
              className="absolute inset-0 bg-stone-900/50"
              onClick={() => setIsDrawerOpen(false)}
            />
            <div className="absolute inset-y-0 start-0 flex w-64 flex-col bg-white p-4 shadow-xl dark:bg-stone-900">
              <div className="mb-6 flex items-center justify-between">
                <BrandMark />
                <button
                  type="button"
                  onClick={() => setIsDrawerOpen(false)}
                  aria-label={t('common.close')}
                  className="rounded-md p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-600 dark:hover:bg-stone-800 dark:hover:text-stone-300"
                >
                  <X className="h-5 w-5" aria-hidden="true" />
                </button>
              </div>
              <NavLinks onNavigate={() => setIsDrawerOpen(false)} />
              <div className="flex items-center gap-2">
                <LanguageSwitcher />
                <ThemeSwitcher />
              </div>
            </div>
          </div>
        )}

        <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `npx vitest run src/components/__tests__/Layout.test.tsx`
Expected: PASS (2/2)

- [ ] **Step 6: Run the full frontend suite to confirm no regressions**

Run: `npm run lint && npx tsc -b && npm test`
Expected: all pass (no other test renders `Layout`, `App.tsx` is unchanged)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/Layout.tsx frontend/src/components/__tests__/Layout.test.tsx \
  frontend/src/i18n/locales/he/translation.json frontend/src/i18n/locales/en/translation.json
git commit -m "Replace top nav bar with a responsive sidebar and mobile drawer"
```

---

### Task 4: Theme-aware chart colors

**Files:**
- Create: `frontend/src/lib/chartColors.ts`
- Test: `frontend/src/lib/__tests__/chartColors.test.ts`
- Modify: `frontend/src/components/CategoryChart.tsx`

**Interfaces:**
- Consumes: `useTheme`, `ResolvedTheme` from Task 2's `ThemeContext`.
- Produces: `getChartColors(theme: ResolvedTheme): ChartColors`.

`recharts` renders its own SVG and never sees Tailwind's `dark:` utility
classes, so its hardcoded hex grid/tick/tooltip colors need to switch based
on the resolved theme via a plain, unit-testable helper function.

- [ ] **Step 1: Write the failing `chartColors` test**

Create `frontend/src/lib/__tests__/chartColors.test.ts`:

```ts
import { describe, expect, it } from 'vitest'

import { getChartColors } from '../chartColors'

describe('getChartColors', () => {
  it('returns light-mode colors for the light theme', () => {
    const colors = getChartColors('light')
    expect(colors.grid).toBe('#e7e5e4')
    expect(colors.tick).toBe('#78716c')
  })

  it('returns dark-mode colors for the dark theme', () => {
    const colors = getChartColors('dark')
    expect(colors.grid).toBe('#44403c')
    expect(colors.tick).toBe('#a8a29e')
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npx vitest run src/lib/__tests__/chartColors.test.ts`
Expected: FAIL — `Cannot find module '../chartColors'`

- [ ] **Step 3: Implement `chartColors`**

Create `frontend/src/lib/chartColors.ts`:

```ts
import type { ResolvedTheme } from '../contexts/ThemeContext'

export interface ChartColors {
  grid: string
  tick: string
  axisLabel: string
  tooltipCursor: string
}

const LIGHT_CHART_COLORS: ChartColors = {
  grid: '#e7e5e4',
  tick: '#78716c',
  axisLabel: '#44403c',
  tooltipCursor: '#f5f5f4',
}

const DARK_CHART_COLORS: ChartColors = {
  grid: '#44403c',
  tick: '#a8a29e',
  axisLabel: '#e7e5e4',
  tooltipCursor: '#292524',
}

export function getChartColors(theme: ResolvedTheme): ChartColors {
  return theme === 'dark' ? DARK_CHART_COLORS : LIGHT_CHART_COLORS
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npx vitest run src/lib/__tests__/chartColors.test.ts`
Expected: PASS (2/2)

- [ ] **Step 5: Wire `CategoryChart` to the resolved theme**

Replace `frontend/src/components/CategoryChart.tsx`:

```tsx
import { useTranslation } from 'react-i18next'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell } from 'recharts'

import type { CategoryTotal } from '../types/dashboard'
import { useTheme } from '../contexts/ThemeContext'
import { colorForCategory } from '../lib/categoryColors'
import { getChartColors } from '../lib/chartColors'
import { formatCurrency } from '../lib/format'

export function CategoryChart({ data, currency }: { data: CategoryTotal[]; currency: string }) {
  const { t, i18n } = useTranslation()
  const { resolvedTheme } = useTheme()
  const colors = getChartColors(resolvedTheme)
  const chartData = data.map((item) => ({
    category: t(`categories.${item.category}`, item.category),
    rawCategory: item.category,
    total: Number(item.total),
  }))

  return (
    <div className="h-72 w-full" dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 24, top: 8, bottom: 8 }}>
          <CartesianGrid horizontal={false} stroke={colors.grid} />
          <XAxis
            type="number"
            tickFormatter={(value: number) => formatCurrency(value, currency, i18n.language)}
            tick={{ fontSize: 12, fill: colors.tick }}
          />
          <YAxis
            type="category"
            dataKey="category"
            width={100}
            orientation={i18n.dir() === 'rtl' ? 'right' : 'left'}
            tick={{ fontSize: 12, fill: colors.axisLabel }}
          />
          <Tooltip
            formatter={(value) => formatCurrency(Number(value), currency, i18n.language)}
            cursor={{ fill: colors.tooltipCursor }}
          />
          <Bar dataKey="total" radius={[0, 4, 4, 0]} barSize={18}>
            {chartData.map((entry) => (
              <Cell key={entry.rawCategory} fill={colorForCategory(entry.rawCategory)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
```

- [ ] **Step 6: Run the full frontend suite to confirm no regressions**

Run: `npm run lint && npx tsc -b && npm test`
Expected: all pass — `DashboardPage.test.tsx` renders `CategoryChart` and now
needs `useTheme()` to resolve; Task 2 Step 11 already put `ThemeProvider`
inside `renderWithProviders`, so this should already be green.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/chartColors.ts frontend/src/lib/__tests__/chartColors.test.ts \
  frontend/src/components/CategoryChart.tsx
git commit -m "Make the category chart's grid/tick colors theme-aware"
```

---

### Task 5: Restyle shared small components

**Files:**
- Modify: `frontend/src/components/StatCard.tsx`
- Modify: `frontend/src/components/ExtractionModeBadge.tsx`
- Modify: `frontend/src/components/StatusStates.tsx`
- Modify: `frontend/src/components/Modal.tsx`
- Modify: `frontend/src/components/FormField.tsx`
- Modify: `frontend/src/components/LanguageSwitcher.tsx`

`CategoryBadge.tsx` needs **no change** — it computes its background from a
categorical hex color at ~10% opacity with the same hex as the text color,
which already reads correctly on both a white and a near-black surface; this
is confirmed visually in Task 7.

These are pure class-name changes (color tokens + `rounded-2xl` cards +
`dark:` variants) with no behavior change, so there's no new test to write —
verification is that the existing suite (which already exercises every one
of these components through the page tests) stays green.

- [ ] **Step 1: Restyle `StatCard.tsx`**

```tsx
import { useTranslation } from 'react-i18next'

import { formatCurrency } from '../lib/format'

export function StatCard({
  label,
  amount,
  currency,
  changePercent,
}: {
  label: string
  amount: number | string
  currency: string
  changePercent?: number | null
}) {
  const { t, i18n } = useTranslation()
  const hasChange = changePercent !== undefined && changePercent !== null
  const isIncrease = hasChange && changePercent! > 0
  const isDecrease = hasChange && changePercent! < 0

  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm dark:border-stone-800 dark:bg-stone-900">
      <p className="text-sm font-medium text-stone-500 dark:text-stone-400">{label}</p>
      <p className="mt-2 text-3xl font-semibold tracking-tight tabular-nums text-stone-900 dark:text-stone-100">
        {formatCurrency(amount, currency, i18n.language)}
      </p>
      {hasChange && (
        <p
          className={[
            'mt-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
            isIncrease
              ? 'bg-danger-500/10 text-danger-700 dark:text-danger-400'
              : isDecrease
                ? 'bg-success-500/10 text-success-700 dark:text-success-400'
                : 'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-400',
          ].join(' ')}
        >
          {isIncrease ? '▲' : isDecrease ? '▼' : '–'} {Math.abs(changePercent!).toFixed(1)}%{' '}
          {t('dashboard.vsLastMonth')}
        </p>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Restyle `ExtractionModeBadge.tsx`**

```tsx
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { getSystemCapabilities } from '../services/systemService'
import type { SystemCapabilities } from '../types/system'

const BADGE_STYLES: Record<SystemCapabilities['receipt_extraction_mode'], { badge: string; dot: string }> = {
  demo: { badge: 'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300', dot: 'bg-stone-400' },
  local: { badge: 'bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-400', dot: 'bg-brand-500' },
  ai: { badge: 'bg-success-50 text-success-700 dark:bg-success-500/10 dark:text-success-400', dot: 'bg-success-500' },
}

export function ExtractionModeBadge() {
  const { t } = useTranslation()
  // Defaults to "demo" while loading or on error — the safe direction is to
  // never claim real AI extraction is active unless the backend confirms it.
  const { data } = useQuery({
    queryKey: ['system-capabilities'],
    queryFn: getSystemCapabilities,
    staleTime: Infinity,
    retry: 1,
  })
  const mode = data?.receipt_extraction_mode ?? 'demo'
  const styles = BADGE_STYLES[mode]

  return (
    <span className={['inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium', styles.badge].join(' ')}>
      <span aria-hidden="true" className={['h-1.5 w-1.5 rounded-full', styles.dot].join(' ')} />
      {t(`uploadReceipt.mode.${mode}`)}
    </span>
  )
}
```

- [ ] **Step 3: Restyle `StatusStates.tsx`**

```tsx
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

export function LoadingState({ label }: { label?: string }) {
  const { t } = useTranslation()
  return (
    <div role="status" className="flex items-center justify-center gap-3 py-16 text-stone-500 dark:text-stone-400">
      <span
        aria-hidden="true"
        className="h-5 w-5 animate-spin rounded-full border-2 border-stone-300 border-t-brand-600 dark:border-stone-700"
      />
      <span>{label ?? t('common.loading')}</span>
    </div>
  )
}

export function ErrorState({
  title,
  message,
  onRetry,
}: {
  title?: string
  message: string
  onRetry?: () => void
}) {
  const { t } = useTranslation()
  return (
    <div role="alert" className="rounded-lg border border-danger-500/30 bg-danger-50 p-4 text-danger-700 dark:bg-danger-500/10 dark:text-danger-400">
      <p className="font-semibold">{title ?? t('common.somethingWentWrong')}</p>
      <p className="mt-1 text-sm">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-md border border-danger-500/40 px-3 py-1.5 text-sm font-medium text-danger-700 hover:bg-danger-500/10 dark:text-danger-400"
        >
          {t('common.tryAgain')}
        </button>
      )}
    </div>
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-stone-300 bg-white px-6 py-16 text-center dark:border-stone-700 dark:bg-stone-900">
      <p className="text-base font-semibold text-stone-900 dark:text-stone-100">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-stone-500 dark:text-stone-400">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
```

- [ ] **Step 4: Restyle `Modal.tsx`**

```tsx
import type { ReactNode } from 'react'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string
  onClose: () => void
  children: ReactNode
}) {
  const { t } = useTranslation()
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        aria-label={t('common.closeDialog')}
        className="absolute inset-0 bg-stone-900/50"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        className="relative max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-6 shadow-xl dark:bg-stone-900"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 id="modal-title" className="text-lg font-semibold text-stone-900 dark:text-stone-100">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('common.close')}
            className="rounded-md p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-600 dark:hover:bg-stone-800 dark:hover:text-stone-300"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Restyle `FormField.tsx`**

```tsx
import type { ReactNode } from 'react'

export function FormField({
  label,
  htmlFor,
  error,
  required,
  children,
  hint,
}: {
  label: string
  htmlFor: string
  error?: string
  required?: boolean
  hint?: string
  children: ReactNode
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="block text-sm font-medium text-stone-700 dark:text-stone-300">
        {label}
        {required && <span className="text-danger-600 dark:text-danger-400"> *</span>}
      </label>
      <div className="mt-1">{children}</div>
      {hint && !error && <p className="mt-1 text-xs text-stone-500 dark:text-stone-400">{hint}</p>}
      {error && (
        <p role="alert" className="mt-1 text-xs text-danger-600 dark:text-danger-400">
          {error}
        </p>
      )}
    </div>
  )
}

export const inputClasses =
  'block w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 shadow-sm placeholder:text-stone-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100 dark:placeholder:text-stone-500'
```

- [ ] **Step 6: Restyle `LanguageSwitcher.tsx`**

Apply the same `slate-*` → `stone-*` + `dark:` substitutions used in Task 2's
`ThemeSwitcher` (which was deliberately modeled on this component) so the two
switchers stay visually identical:

```tsx
import { Check, Globe } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { SUPPORTED_LANGUAGES, type SupportedLanguage } from '../i18n'

const LABEL_KEY: Record<SupportedLanguage, 'hebrew' | 'english'> = {
  he: 'hebrew',
  en: 'english',
}

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation()
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const optionRefs = useRef<Partial<Record<SupportedLanguage, HTMLButtonElement | null>>>({})
  const currentLanguage = i18n.language as SupportedLanguage

  useEffect(() => {
    if (!isOpen) return

    function handlePointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsOpen(false)
        triggerRef.current?.focus()
      }
    }
    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen])

  useEffect(() => {
    if (isOpen) {
      optionRefs.current[currentLanguage]?.focus()
    }
    // Only re-focus when the menu newly opens, not on every language change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen])

  function selectLanguage(language: SupportedLanguage) {
    void i18n.changeLanguage(language)
    setIsOpen(false)
    triggerRef.current?.focus()
  }

  function handleOptionKeyDown(event: React.KeyboardEvent, index: number) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const direction = event.key === 'ArrowDown' ? 1 : -1
      const nextIndex = (index + direction + SUPPORTED_LANGUAGES.length) % SUPPORTED_LANGUAGES.length
      optionRefs.current[SUPPORTED_LANGUAGES[nextIndex]]?.focus()
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-label={t('language.changeLanguage')}
        title={t('language.changeLanguage')}
        className="flex h-9 w-9 items-center justify-center rounded-md border border-stone-300 bg-white text-stone-600 shadow-sm transition-colors hover:bg-stone-100 hover:text-stone-900 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-300 dark:hover:bg-stone-800 dark:hover:text-stone-100"
      >
        <Globe className="h-4 w-4" aria-hidden="true" />
      </button>

      {isOpen && (
        <div
          role="listbox"
          aria-label={t('language.switcherLabel')}
          className="absolute end-0 z-20 mt-2 w-40 overflow-hidden rounded-md border border-stone-200 bg-white py-1 shadow-lg dark:border-stone-700 dark:bg-stone-900"
        >
          {SUPPORTED_LANGUAGES.map((language, index) => {
            const isSelected = currentLanguage === language
            return (
              <button
                key={language}
                ref={(element) => {
                  optionRefs.current[language] = element
                }}
                type="button"
                role="option"
                aria-selected={isSelected}
                data-testid={`language-option-${language}`}
                tabIndex={isSelected ? 0 : -1}
                onClick={() => selectLanguage(language)}
                onKeyDown={(event) => handleOptionKeyDown(event, index)}
                className={[
                  'flex w-full items-center justify-between gap-2 px-3 py-2 text-sm transition-colors focus:outline-none focus:bg-stone-100 dark:focus:bg-stone-800',
                  isSelected
                    ? 'font-medium text-brand-700 dark:text-brand-400'
                    : 'text-stone-700 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800',
                ].join(' ')}
              >
                <span>{t(`language.${LABEL_KEY[language]}`)}</span>
                {isSelected && <Check className="h-4 w-4 text-brand-600 dark:text-brand-400" aria-hidden="true" />}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 7: Run the full frontend suite to confirm no regressions**

Run: `npm run lint && npx tsc -b && npm test`
Expected: all pass — only class names changed; every assertion in the
existing suite targets text, roles, or behavior.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/StatCard.tsx frontend/src/components/ExtractionModeBadge.tsx \
  frontend/src/components/StatusStates.tsx frontend/src/components/Modal.tsx \
  frontend/src/components/FormField.tsx frontend/src/components/LanguageSwitcher.tsx
git commit -m "Restyle shared UI components with the new palette and dark mode"
```

---

### Task 6: Restyle forms, lists, receipt components, and pages

**Files:**
- Modify: `frontend/src/components/ExpenseList.tsx`
- Modify: `frontend/src/components/ReceiptDropzone.tsx`
- Modify: `frontend/src/components/ReceiptImage.tsx`
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/pages/ExpensesPage.tsx`
- Modify: `frontend/src/pages/AddExpensePage.tsx`
- Modify: `frontend/src/pages/UploadReceiptPage.tsx`
- Modify: `frontend/src/pages/AssistantPage.tsx`

`ExpenseForm.tsx` needs **no change** — every color class it uses is either
`danger-*`/`brand-*` (retokenized in Task 1, so it already picked up the new
teal/red automatically) or comes from `FormField`'s `inputClasses` (restyled
in Task 5), and solid-color buttons don't need `dark:` variants since their
own background/text contrast doesn't depend on the surrounding page theme.

Same as Task 5: pure class-name changes, no behavior change, no new tests —
verify via the existing suite.

- [ ] **Step 1: Restyle `ExpenseList.tsx`**

```tsx
import { useTranslation } from 'react-i18next'

import type { Expense } from '../types/expense'
import { CategoryBadge } from './CategoryBadge'
import { formatCurrency, formatDate } from '../lib/format'

export function ExpenseList({
  expenses,
  onEdit,
  onDelete,
  onViewReceipt,
}: {
  expenses: Expense[]
  onEdit: (expense: Expense) => void
  onDelete: (expense: Expense) => void
  onViewReceipt: (expense: Expense) => void
}) {
  const { t, i18n } = useTranslation()

  return (
    <div className="overflow-x-auto rounded-2xl border border-stone-200 bg-white shadow-sm dark:border-stone-800 dark:bg-stone-900">
      <table className="min-w-full divide-y divide-stone-200 text-sm dark:divide-stone-800">
        <thead className="bg-stone-50 dark:bg-stone-800/50">
          <tr>
            <th scope="col" className="px-4 py-3 text-left font-medium text-stone-500 dark:text-stone-400">
              {t('expenses.columnBusiness')}
            </th>
            <th scope="col" className="px-4 py-3 text-left font-medium text-stone-500 dark:text-stone-400">
              {t('expenses.columnCategory')}
            </th>
            <th scope="col" className="px-4 py-3 text-left font-medium text-stone-500 dark:text-stone-400">
              {t('expenses.columnDate')}
            </th>
            <th scope="col" className="px-4 py-3 text-right font-medium text-stone-500 dark:text-stone-400">
              {t('expenses.columnAmount')}
            </th>
            <th scope="col" className="px-4 py-3 text-right font-medium text-stone-500 dark:text-stone-400">
              <span className="sr-only">{t('expenses.columnActions')}</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
          {expenses.map((expense) => (
            <tr key={expense.id} className="hover:bg-stone-50 dark:hover:bg-stone-800/50">
              <td className="px-4 py-3">
                <p className="font-medium text-stone-900 dark:text-stone-100">{expense.business_name}</p>
                {expense.receipt_number && (
                  <p className="text-xs text-stone-400 dark:text-stone-500">#{expense.receipt_number}</p>
                )}
              </td>
              <td className="px-4 py-3">
                <CategoryBadge category={expense.category} />
              </td>
              <td className="px-4 py-3 text-stone-600 dark:text-stone-400">{formatDate(expense.expense_date, i18n.language)}</td>
              <td className="px-4 py-3 text-right font-medium tabular-nums text-stone-900 dark:text-stone-100">
                {formatCurrency(expense.amount, expense.currency, i18n.language)}
              </td>
              <td className="px-4 py-3">
                <div className="flex justify-end gap-2">
                  {expense.receipt_image_url && (
                    <button
                      type="button"
                      onClick={() => onViewReceipt(expense)}
                      className="rounded-md px-2 py-1 text-xs font-medium text-stone-600 hover:bg-stone-100 dark:text-stone-400 dark:hover:bg-stone-800"
                      aria-label={t('expenses.viewReceiptAction', { name: expense.business_name })}
                    >
                      {t('expenses.viewReceipt')}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => onEdit(expense)}
                    className="rounded-md px-2 py-1 text-xs font-medium text-brand-700 hover:bg-brand-50 dark:text-brand-400 dark:hover:bg-brand-500/10"
                    aria-label={t('expenses.editAction', { name: expense.business_name })}
                  >
                    {t('common.edit')}
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(expense)}
                    className="rounded-md px-2 py-1 text-xs font-medium text-danger-600 hover:bg-danger-50 dark:text-danger-400 dark:hover:bg-danger-500/10"
                    aria-label={t('expenses.deleteAction', { name: expense.business_name })}
                  >
                    {t('common.delete')}
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 2: Restyle `ReceiptDropzone.tsx`**

```tsx
import { useCallback, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp']

export function ReceiptDropzone({
  onFileSelected,
  previewUrl,
}: {
  onFileSelected: (file: File) => void
  previewUrl: string | null
}) {
  const { t } = useTranslation()
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)

  const handleFiles = useCallback(
    (files: FileList | null) => {
      const file = files?.[0]
      if (!file) return
      if (!ACCEPTED_TYPES.includes(file.type)) return
      onFileSelected(file)
    },
    [onFileSelected],
  )

  return (
    <div>
      <div
        onDragOver={(event) => {
          event.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setIsDragging(false)
          handleFiles(event.dataTransfer.files)
        }}
        className={[
          'flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 text-center transition-colors',
          isDragging
            ? 'border-brand-500 bg-brand-50 dark:bg-brand-500/10'
            : 'border-stone-300 bg-white dark:border-stone-700 dark:bg-stone-900',
        ].join(' ')}
      >
        {previewUrl ? (
          <img
            src={previewUrl}
            alt={t('uploadReceipt.previewAlt')}
            className="max-h-64 rounded-lg border border-stone-200 object-contain dark:border-stone-700"
          />
        ) : (
          <p className="text-sm text-stone-500 dark:text-stone-400">{t('uploadReceipt.dropzoneText')}</p>
        )}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="mt-4 inline-flex items-center rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-medium text-stone-700 shadow-sm hover:bg-stone-50 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-200 dark:hover:bg-stone-700"
        >
          {previewUrl ? t('uploadReceipt.chooseDifferentImage') : t('uploadReceipt.chooseImage')}
        </button>
        <p className="mt-2 text-xs text-stone-400 dark:text-stone-500">{t('uploadReceipt.fileHint')}</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_TYPES.join(',')}
          className="sr-only"
          aria-label={t('uploadReceipt.chooseImage')}
          onChange={(event) => handleFiles(event.target.files)}
        />
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Restyle `ReceiptImage.tsx`**

```tsx
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

/**
 * Renders a receipt image from a (possibly time-limited, e.g. Supabase signed)
 * URL. If the URL has expired or is otherwise unreachable, the browser's <img>
 * onerror event fires and we swap to a plain-text fallback instead of a broken
 * image icon — the underlying receipt data is never lost, only the preview.
 */
export function ReceiptImage({ url, alt }: { url: string; alt: string }) {
  const { t } = useTranslation()
  const [failed, setFailed] = useState(false)

  if (failed) {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-stone-300 bg-stone-50 text-sm text-stone-500 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-400">
        {t('expenses.receiptImageUnavailable')}
      </div>
    )
  }

  return (
    <img
      src={url}
      alt={alt}
      onError={() => setFailed(true)}
      className="max-h-[70vh] w-full rounded-lg border border-stone-200 object-contain dark:border-stone-700"
    />
  )
}
```

- [ ] **Step 4: Restyle `DashboardPage.tsx`**

```tsx
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { StatCard } from '../components/StatCard'
import { CategoryChart } from '../components/CategoryChart'
import { EmptyState, ErrorState, LoadingState } from '../components/StatusStates'
import { CategoryBadge } from '../components/CategoryBadge'
import { getDashboardStats } from '../services/dashboardService'
import { formatCurrency, formatDate } from '../lib/format'
import { toApiError } from '../services/apiClient'

export function DashboardPage() {
  const { t, i18n } = useTranslation()
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  })

  if (isLoading) return <LoadingState label={t('common.loading')} />

  if (isError) {
    return <ErrorState message={toApiError(error).message} onRetry={() => refetch()} />
  }

  if (!data) return null

  const hasAnyExpenses = data.recent_expenses.length > 0 || data.totals_by_category.length > 0
  const currency = data.recent_expenses[0]?.currency ?? 'ILS'

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">{t('dashboard.title')}</h1>
        <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('dashboard.subtitle')}</p>
      </div>

      {!hasAnyExpenses ? (
        <EmptyState
          title={t('dashboard.emptyTitle')}
          description={t('dashboard.emptyDescription')}
          action={
            <div className="flex justify-center gap-3">
              <Link
                to="/add-expense"
                className="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
              >
                {t('nav.addExpense')}
              </Link>
              <Link
                to="/upload-receipt"
                className="rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-200 dark:hover:bg-stone-700"
              >
                {t('nav.uploadReceipt')}
              </Link>
            </div>
          }
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <StatCard
              label={t('dashboard.thisMonth')}
              amount={data.current_month_total}
              currency={currency}
              changePercent={data.percentage_change}
            />
            <StatCard label={t('dashboard.lastMonth')} amount={data.previous_month_total} currency={currency} />
          </div>

          {data.totals_by_category.length > 0 && (
            <div className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm dark:border-stone-800 dark:bg-stone-900">
              <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">{t('dashboard.spendingByCategory')}</h2>
              <p className="text-sm text-stone-500 dark:text-stone-400">{t('dashboard.currentMonth')}</p>
              <div className="mt-4">
                <CategoryChart data={data.totals_by_category} currency={currency} />
              </div>
            </div>
          )}

          <div className="rounded-2xl border border-stone-200 bg-white shadow-sm dark:border-stone-800 dark:bg-stone-900">
            <div className="flex items-center justify-between border-b border-stone-100 px-5 py-4 dark:border-stone-800">
              <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">{t('dashboard.recentExpenses')}</h2>
              <Link to="/expenses" className="text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300">
                {t('dashboard.viewAll')}
              </Link>
            </div>
            <ul className="divide-y divide-stone-100 dark:divide-stone-800">
              {data.recent_expenses.map((expense) => (
                <li key={expense.id} className="flex items-center justify-between gap-4 px-5 py-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-stone-900 dark:text-stone-100">{expense.business_name}</p>
                    <p className="text-xs text-stone-500 dark:text-stone-400">{formatDate(expense.expense_date, i18n.language)}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <CategoryBadge category={expense.category} />
                    <span className="font-medium tabular-nums text-stone-900 dark:text-stone-100">
                      {formatCurrency(expense.amount, expense.currency, i18n.language)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Restyle `ExpensesPage.tsx`**

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'

import { ExpenseForm } from '../components/ExpenseForm'
import { ExpenseList } from '../components/ExpenseList'
import { Modal } from '../components/Modal'
import { ReceiptImage } from '../components/ReceiptImage'
import { EmptyState, ErrorState, LoadingState } from '../components/StatusStates'
import { inputClasses } from '../components/FormField'
import { deleteExpense, listExpenses, updateExpense } from '../services/expenseService'
import { toApiError } from '../services/apiClient'
import type { ExpenseFormInput, ExpenseFormValues } from '../schemas/expense'
import { EXPENSE_CATEGORIES, type Expense, type ExpenseCategory } from '../types/expense'

function expenseToFormValues(expense: Expense): ExpenseFormInput {
  return {
    business_name: expense.business_name,
    receipt_number: expense.receipt_number ?? '',
    amount: expense.amount,
    vat_amount: expense.vat_amount ?? '',
    currency: expense.currency,
    category: expense.category,
    expense_date: expense.expense_date,
    payment_method: expense.payment_method ?? '',
    notes: expense.notes ?? '',
  }
}

export function ExpensesPage() {
  const { t } = useTranslation()
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState<ExpenseCategory | ''>('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [editingExpense, setEditingExpense] = useState<Expense | null>(null)
  const [deletingExpense, setDeletingExpense] = useState<Expense | null>(null)
  const [viewingReceiptExpense, setViewingReceiptExpense] = useState<Expense | null>(null)

  const queryClient = useQueryClient()
  const filters = { search, category, date_from: dateFrom, date_to: dateTo }

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['expenses', filters],
    queryFn: () => listExpenses(filters),
  })

  const updateMutation = useMutation({
    mutationFn: (values: ExpenseFormValues) => {
      if (!editingExpense) throw new Error('No expense selected')
      return updateExpense(editingExpense.id, {
        ...values,
        receipt_number: values.receipt_number || null,
        vat_amount: values.vat_amount === '' ? null : Number(values.vat_amount),
        payment_method: values.payment_method || null,
        notes: values.notes || null,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      setEditingExpense(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteExpense(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      setDeletingExpense(null)
    },
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">{t('expenses.title')}</h1>
        <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('expenses.subtitle')}</p>
      </div>

      <div className="flex flex-col gap-3 rounded-2xl border border-stone-200 bg-white p-4 shadow-sm sm:flex-row sm:flex-wrap dark:border-stone-800 dark:bg-stone-900">
        <div className="min-w-0 sm:flex-[2_2_240px]">
          <label htmlFor="search" className="sr-only">
            {t('expenses.searchLabel')}
          </label>
          <input
            id="search"
            className={inputClasses}
            placeholder={t('expenses.searchPlaceholder')}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <div className="min-w-0 sm:flex-1 sm:basis-40">
          <label htmlFor="category-filter" className="sr-only">
            {t('expenses.categoryFilterLabel')}
          </label>
          <select
            id="category-filter"
            className={inputClasses}
            value={category}
            onChange={(event) => setCategory(event.target.value as ExpenseCategory | '')}
          >
            <option value="">{t('expenses.allCategories')}</option>
            {EXPENSE_CATEGORIES.map((item) => (
              <option key={item} value={item}>
                {t(`categories.${item}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="flex min-w-0 gap-2 sm:flex-1 sm:basis-56">
          <input
            aria-label={t('expenses.dateFromLabel')}
            type="date"
            className={`${inputClasses} min-w-0 flex-1`}
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
          />
          <input
            aria-label={t('expenses.dateToLabel')}
            type="date"
            className={`${inputClasses} min-w-0 flex-1`}
            value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
          />
        </div>
      </div>

      {isLoading && <LoadingState />}
      {isError && <ErrorState message={toApiError(error).message} onRetry={() => refetch()} />}
      {!isLoading && !isError && data && data.length === 0 && (
        <EmptyState title={t('expenses.emptyTitle')} description={t('expenses.emptyDescription')} />
      )}
      {!isLoading && !isError && data && data.length > 0 && (
        <ExpenseList
          expenses={data}
          onEdit={setEditingExpense}
          onDelete={setDeletingExpense}
          onViewReceipt={setViewingReceiptExpense}
        />
      )}

      {viewingReceiptExpense && viewingReceiptExpense.receipt_image_url && (
        <Modal
          title={t('expenses.viewReceiptTitle', { name: viewingReceiptExpense.business_name })}
          onClose={() => setViewingReceiptExpense(null)}
        >
          <ReceiptImage
            url={viewingReceiptExpense.receipt_image_url}
            alt={t('expenses.receiptImageAlt', { name: viewingReceiptExpense.business_name })}
          />
        </Modal>
      )}

      {editingExpense && (
        <Modal title={t('expenses.editTitle')} onClose={() => setEditingExpense(null)}>
          <ExpenseForm
            defaultValues={expenseToFormValues(editingExpense)}
            submitLabel={t('expenses.saveChanges')}
            isSubmitting={updateMutation.isPending}
            submitError={updateMutation.isError ? toApiError(updateMutation.error).message : null}
            onSubmit={(values) => updateMutation.mutate(values)}
          />
        </Modal>
      )}

      {deletingExpense && (
        <Modal title={t('expenses.deleteTitle')} onClose={() => setDeletingExpense(null)}>
          <p className="text-sm text-stone-600 dark:text-stone-400">
            <Trans
              i18nKey="expenses.deleteConfirm"
              values={{ name: deletingExpense.business_name }}
              components={{ bold: <strong /> }}
            />
          </p>
          {deleteMutation.isError && (
            <p role="alert" className="mt-2 text-sm text-danger-600 dark:text-danger-400">
              {toApiError(deleteMutation.error).message}
            </p>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setDeletingExpense(null)}
              className="rounded-md border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:text-stone-200 dark:hover:bg-stone-800"
            >
              {t('common.cancel')}
            </button>
            <button
              type="button"
              disabled={deleteMutation.isPending}
              onClick={() => {
                if (deleteMutation.isPending) return
                deleteMutation.mutate(deletingExpense.id)
              }}
              className="rounded-md bg-danger-600 px-4 py-2 text-sm font-semibold text-white hover:bg-danger-700 disabled:opacity-60"
            >
              {deleteMutation.isPending ? t('common.deleting') : t('common.delete')}
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
```

- [ ] **Step 6: Restyle `AddExpensePage.tsx`**

```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { ExpenseForm } from '../components/ExpenseForm'
import { createExpense } from '../services/expenseService'
import { toApiError } from '../services/apiClient'
import type { ExpenseFormValues } from '../schemas/expense'

export function AddExpensePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showSuccess, setShowSuccess] = useState(false)

  const mutation = useMutation({
    mutationFn: (values: ExpenseFormValues) =>
      createExpense({
        ...values,
        receipt_number: values.receipt_number || null,
        vat_amount: values.vat_amount === '' ? null : Number(values.vat_amount),
        payment_method: values.payment_method || null,
        notes: values.notes || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      setShowSuccess(true)
      setTimeout(() => navigate('/expenses'), 900)
    },
  })

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">{t('addExpense.title')}</h1>
        <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('addExpense.subtitle')}</p>
      </div>

      {showSuccess && (
        <div
          role="status"
          className="rounded-lg border border-success-500/30 bg-success-50 p-3 text-sm text-success-700 dark:bg-success-500/10 dark:text-success-400"
        >
          {t('addExpense.successMessage')}
        </div>
      )}

      <div className="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm dark:border-stone-800 dark:bg-stone-900">
        <ExpenseForm
          onSubmit={(values) => {
            if (mutation.isPending) return
            mutation.mutate(values)
          }}
          isSubmitting={mutation.isPending}
          submitError={mutation.isError ? toApiError(mutation.error).message : null}
        />
      </div>
    </div>
  )
}
```

- [ ] **Step 7: Restyle `UploadReceiptPage.tsx`**

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { ExpenseForm } from '../components/ExpenseForm'
import { ExtractionModeBadge } from '../components/ExtractionModeBadge'
import { ReceiptDropzone } from '../components/ReceiptDropzone'
import { LoadingState } from '../components/StatusStates'
import { uploadReceipt, confirmReceipt } from '../services/receiptService'
import { getSystemCapabilities } from '../services/systemService'
import { toApiError } from '../services/apiClient'
import type { ExpenseFormInput, ExpenseFormValues } from '../schemas/expense'
import type { ExtractedReceiptData, ReceiptUploadResponse } from '../types/receipt'
import { groupWarnings, type WarningGroup } from '../lib/warnings'

// Below this quality-score threshold, so little was extracted that showing
// the ordinary "review and confirm" heading (with a near-0% badge) next to
// an almost entirely empty form would read as if something went wrong with
// the form itself, rather than "we just couldn't read this receipt well".
const INSUFFICIENT_EXTRACTION_THRESHOLD = 0.15

const WARNING_GROUP_STYLES: Record<WarningGroup, string> = {
  recovered: 'border-sky-400/40 bg-sky-50 text-sky-800 dark:bg-sky-500/10 dark:text-sky-300',
  review: 'border-amber-400/40 bg-amber-50 text-amber-800 dark:bg-amber-500/10 dark:text-amber-300',
  attention: 'border-stone-300 bg-stone-50 text-stone-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-400',
}

// An unrecognized amount/date must never be silently replaced with 0 or
// today's date — either would look like a real extracted value instead of
// the "we couldn't read this" signal it actually is. Leaving the field
// empty forces the (already-required) form validation to visibly prompt the
// user for it, instead of letting a wrong guess slip through unnoticed.
function extractedToFormValues(data: ExtractedReceiptData | null): Partial<ExpenseFormInput> {
  if (!data) return {}
  return {
    business_name: data.business_name ?? '',
    receipt_number: data.receipt_number ?? '',
    amount: data.total ?? '',
    vat_amount: data.vat ?? '',
    currency: data.currency || 'ILS',
    category: data.category,
    expense_date: data.date ?? '',
  }
}

/** Maps a known API error status to a translation key for a clearer user-facing message. */
function confirmErrorKey(status: number | undefined): string | null {
  if (status === 409) return 'uploadReceipt.errors.alreadyConfirmed'
  if (status === 410) return 'uploadReceipt.errors.uploadExpired'
  if (status === 404) return 'uploadReceipt.errors.uploadNotFound'
  return null
}

export function UploadReceiptPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [uploadResult, setUploadResult] = useState<ReceiptUploadResponse | null>(null)
  const [showSuccess, setShowSuccess] = useState(false)

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null)
      return
    }
    const objectUrl = URL.createObjectURL(file)
    setPreviewUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [file])

  const uploadMutation = useMutation({
    mutationFn: uploadReceipt,
    onSuccess: (result) => setUploadResult(result),
  })

  const confirmMutation = useMutation({
    mutationFn: confirmReceipt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      setShowSuccess(true)
      setTimeout(() => navigate('/expenses'), 900)
    },
  })

  function handleFileSelected(selectedFile: File) {
    if (uploadMutation.isPending) return
    setFile(selectedFile)
    setUploadResult(null)
    uploadMutation.mutate(selectedFile)
  }

  function handleConfirm(values: ExpenseFormValues) {
    if (!uploadResult || confirmMutation.isPending) return
    confirmMutation.mutate({
      upload_id: uploadResult.upload_id,
      business_name: values.business_name,
      receipt_number: values.receipt_number || null,
      amount: Number(values.amount),
      vat_amount: values.vat_amount === '' ? null : Number(values.vat_amount),
      currency: values.currency,
      category: values.category,
      expense_date: values.expense_date,
      payment_method: values.payment_method || null,
      notes: values.notes || null,
      extraction_confidence: uploadResult.extracted_data?.confidence ?? null,
    })
  }

  const confidence = uploadResult?.extracted_data?.confidence
  const warningGroups = groupWarnings(uploadResult?.extracted_data?.warnings ?? [])
  const isInsufficientExtraction =
    uploadResult?.extraction_succeeded === true &&
    typeof confidence === 'number' &&
    confidence < INSUFFICIENT_EXTRACTION_THRESHOLD
  const confirmError = confirmMutation.isError ? toApiError(confirmMutation.error) : null
  const confirmErrorTranslationKey = confirmError ? confirmErrorKey(confirmError.status) : null

  const { data: capabilities } = useQuery({
    queryKey: ['system-capabilities'],
    queryFn: getSystemCapabilities,
    staleTime: Infinity,
    retry: 1,
  })
  const showOllamaUnavailableWarning =
    capabilities?.receipt_extraction_mode === 'local' && capabilities.ollama_available === false

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">{t('uploadReceipt.title')}</h1>
          <ExtractionModeBadge />
        </div>
        <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('uploadReceipt.subtitle')}</p>
      </div>

      {showOllamaUnavailableWarning && (
        <div
          role="alert"
          className="rounded-lg border border-amber-400/40 bg-amber-50 p-4 text-sm text-amber-800 dark:bg-amber-500/10 dark:text-amber-300"
        >
          {t('uploadReceipt.errors.ollamaUnavailable')}
        </div>
      )}

      {showSuccess && (
        <div
          role="status"
          className="rounded-lg border border-success-500/30 bg-success-50 p-3 text-sm text-success-700 dark:bg-success-500/10 dark:text-success-400"
        >
          {t('uploadReceipt.successMessage')}
        </div>
      )}

      <div className="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm dark:border-stone-800 dark:bg-stone-900">
        <ReceiptDropzone onFileSelected={handleFileSelected} previewUrl={previewUrl} />
      </div>

      {uploadMutation.isPending && <LoadingState label={t('uploadReceipt.analyzing')} />}

      {uploadMutation.isError && (
        <div role="alert" className="rounded-lg border border-danger-500/30 bg-danger-50 p-4 text-sm text-danger-700 dark:bg-danger-500/10 dark:text-danger-400">
          <p className="font-semibold">{t('uploadReceipt.uploadFailedTitle')}</p>
          <p className="mt-1">{toApiError(uploadMutation.error).message}</p>
        </div>
      )}

      {uploadResult && !uploadResult.extraction_succeeded && (
        <div className="rounded-lg border border-amber-400/40 bg-amber-50 p-4 text-sm text-amber-800 dark:bg-amber-500/10 dark:text-amber-300">
          <p className="font-semibold">{t('uploadReceipt.extractionFailedTitle')}</p>
          <p className="mt-1">{t('uploadReceipt.extractionFailedBody')}</p>
        </div>
      )}

      {uploadResult && uploadResult.extraction_succeeded && isInsufficientExtraction && (
        <div className="rounded-lg border border-amber-400/40 bg-amber-50 p-4 text-sm text-amber-800 dark:bg-amber-500/10 dark:text-amber-300">
          <p className="font-semibold">{t('uploadReceipt.insufficientExtractionTitle')}</p>
          <p className="mt-1">{t('uploadReceipt.insufficientExtractionBody')}</p>
        </div>
      )}

      {uploadResult && (
        <div className="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm dark:border-stone-800 dark:bg-stone-900">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">{t('uploadReceipt.reviewAndConfirm')}</h2>
            {typeof confidence === 'number' && !isInsufficientExtraction && (
              <span
                className="rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-medium text-brand-700 dark:bg-brand-500/10 dark:text-brand-400"
                title={t('uploadReceipt.qualityScoreExplanation')}
              >
                {t('uploadReceipt.qualityScore', { value: Math.round(confidence * 100) })}
              </span>
            )}
          </div>

          {(['review', 'attention', 'recovered'] as const).map((group) =>
            warningGroups[group].length > 0 ? (
              <div key={group} className={`mb-3 rounded-lg border p-3 text-xs ${WARNING_GROUP_STYLES[group]}`}>
                <p className="mb-1 font-semibold">{t(`uploadReceipt.warningGroups.${group}`)}</p>
                <ul className="space-y-1">
                  {warningGroups[group].map((warning) => (
                    <li key={warning}>
                      {t(`uploadReceipt.warnings.${warning}`, t('uploadReceipt.warnings.extraction_incomplete'))}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null,
          )}

          {confirmError && (
            <div
              role="alert"
              className="mb-4 rounded-lg border border-danger-500/30 bg-danger-50 p-3 text-sm text-danger-700 dark:bg-danger-500/10 dark:text-danger-400"
            >
              <p>{confirmErrorTranslationKey ? t(confirmErrorTranslationKey) : confirmError.message}</p>
              {confirmErrorTranslationKey === 'uploadReceipt.errors.alreadyConfirmed' && (
                <Link to="/expenses" className="mt-1 inline-block font-medium underline">
                  {t('dashboard.viewAll')}
                </Link>
              )}
            </div>
          )}

          <ExpenseForm
            key={uploadResult.upload_id}
            defaultValues={extractedToFormValues(uploadResult.extracted_data)}
            submitLabel={t('uploadReceipt.confirmAndSave')}
            isSubmitting={confirmMutation.isPending}
            onSubmit={handleConfirm}
          />
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 8: Restyle `AssistantPage.tsx`**

```tsx
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { sendChatMessage } from '../services/assistantService'
import type { ChatMessage } from '../types/assistant'

export function AssistantPage() {
  const { t } = useTranslation()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const exampleQuestions = [
    t('assistant.exampleQuestion1'),
    t('assistant.exampleQuestion2'),
    t('assistant.exampleQuestion3'),
  ]

  async function send(question: string) {
    const trimmed = question.trim()
    if (!trimmed || isSending) return

    const history = messages
    const userMessage: ChatMessage = { role: 'user', content: trimmed }
    setMessages([...history, userMessage])
    setInput('')
    setError(null)
    setIsSending(true)
    try {
      const reply = await sendChatMessage(trimmed, history)
      setMessages([...history, userMessage, { role: 'assistant', content: reply }])
    } catch {
      // Always the translated, generic message — never the raw backend
      // detail text, which may be untranslated/technical (matches the
      // "never leak the raw provider error" rule the backend route itself
      // already follows for this endpoint).
      setError(t('assistant.errorMessage'))
    } finally {
      setIsSending(false)
    }
  }

  return (
    <div className="mx-auto flex h-[70vh] max-w-2xl flex-col">
      <div>
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">{t('assistant.title')}</h1>
        <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('assistant.subtitle')}</p>
      </div>

      <div className="mt-6 flex-1 space-y-3 overflow-y-auto rounded-2xl border border-stone-200 bg-white p-4 shadow-sm dark:border-stone-800 dark:bg-stone-900">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <p className="text-sm font-medium text-stone-700 dark:text-stone-300">{t('assistant.emptyTitle')}</p>
            <div className="flex flex-wrap justify-center gap-2">
              {exampleQuestions.map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => send(question)}
                  className="rounded-full border border-stone-300 px-3 py-1.5 text-sm text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:text-stone-300 dark:hover:bg-stone-800"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, index) => (
            <div key={index} className={msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
              <p
                className={
                  msg.role === 'user'
                    ? 'max-w-[80%] rounded-lg bg-brand-600 px-3 py-2 text-sm text-white'
                    : 'max-w-[80%] rounded-lg bg-stone-100 px-3 py-2 text-sm text-stone-900 dark:bg-stone-800 dark:text-stone-100'
                }
              >
                {msg.content}
              </p>
            </div>
          ))
        )}
        {error && <p className="text-sm text-danger-700 dark:text-danger-400">{error}</p>}
      </div>

      <form
        className="mt-4 flex gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          send(input)
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={t('assistant.inputPlaceholder')}
          className="flex-1 rounded-lg border border-stone-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100"
        />
        <button
          type="submit"
          disabled={isSending}
          className="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {t('assistant.send')}
        </button>
      </form>
    </div>
  )
}
```

- [ ] **Step 9: Run the full frontend suite to confirm no regressions**

Run: `npm run lint && npx tsc -b && npm test && npm run build`
Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/ExpenseList.tsx frontend/src/components/ReceiptDropzone.tsx \
  frontend/src/components/ReceiptImage.tsx frontend/src/pages/DashboardPage.tsx \
  frontend/src/pages/ExpensesPage.tsx frontend/src/pages/AddExpensePage.tsx \
  frontend/src/pages/UploadReceiptPage.tsx frontend/src/pages/AssistantPage.tsx
git commit -m "Restyle forms, lists, receipt components, and all pages"
```

---

### Task 7: Full verification and live browser check

**Files:** none (verification-only task).

- [ ] **Step 1: Run the full frontend suite**

Run: `npm run lint && npx tsc -b && npm test && npm run build`
Expected: all pass. (No backend files changed in this plan, so the backend
`pytest` suite doesn't need re-running.)

- [ ] **Step 2: Live browser check — light mode, Hebrew**

Start the frontend dev server, open the app, and visually confirm on
Dashboard, Expenses, and the AI Assistant page:
- Rubik font is visibly loaded (check via devtools computed font-family, or
  just that Hebrew text no longer looks like the system fallback).
- Sidebar is visible with all 5 nav items and correct RTL placement (on the
  right edge).
- Teal primary color and rounded-2xl cards are visible.

- [ ] **Step 3: Live browser check — dark mode, Hebrew**

Click the new theme switcher, select "כהה" (dark), and confirm every visited
page switches to the stone-950/900 dark surfaces with readable text, no
white flashes or unstyled elements.

- [ ] **Step 4: Live browser check — light and dark mode, English**

Switch the language to English via the existing language switcher and repeat
a quick pass in both themes — confirm LTR layout is correct (sidebar on the
left) and nothing broke.

- [ ] **Step 5: Live browser check — mobile viewport drawer**

Resize the browser preview to a mobile width, confirm the sidebar collapses
to the top bar + hamburger, open the drawer, confirm it closes via the
backdrop click and via Escape.

- [ ] **Step 6: Fix any issues found**

If the live check surfaces a real bug, fix it, add or update a test if the
bug was behavioral (not purely visual), and commit the fix separately.

- [ ] **Step 7: Finish the branch**

Invoke `superpowers:finishing-a-development-branch`.
