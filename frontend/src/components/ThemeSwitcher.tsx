import { Moon, Sun } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { useTheme } from '../contexts/ThemeContext'

export function ThemeSwitcher() {
  const { t } = useTranslation()
  const { resolvedTheme, setMode } = useTheme()
  const isDark = resolvedTheme === 'dark'

  return (
    <button
      type="button"
      onClick={() => setMode(isDark ? 'light' : 'dark')}
      aria-label={t('theme.changeTheme')}
      aria-pressed={isDark}
      title={t('theme.changeTheme')}
      className="grid h-9 w-9 place-items-center rounded-lg text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
    >
      {isDark ? <Sun className="h-4 w-4" aria-hidden="true" /> : <Moon className="h-4 w-4" aria-hidden="true" />}
    </button>
  )
}
