import { Check, Moon, Sun, SunMoon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useTheme, type ThemeMode } from '../contexts/ThemeContext'

const MODE_ICON: Record<ThemeMode, typeof Sun> = {
  light: Sun,
  dark: Moon,
  system: SunMoon,
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
          className="absolute start-0 bottom-full z-20 mb-2 w-40 overflow-hidden rounded-md border border-stone-200 bg-white py-1 shadow-lg dark:border-stone-700 dark:bg-stone-900"
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
