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
        className="grid h-9 w-9 place-items-center rounded-lg text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
      >
        <Globe className="h-4 w-4" aria-hidden="true" />
      </button>

      {isOpen && (
        <div
          role="listbox"
          aria-label={t('language.switcherLabel')}
          className="absolute start-0 bottom-full z-20 mb-2 w-44 animate-pop-in overflow-hidden rounded-xl border border-zinc-200 bg-white p-1 shadow-raised dark:border-zinc-700 dark:bg-zinc-900"
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
                  'flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm transition-colors focus:bg-zinc-100 dark:focus:bg-zinc-800',
                  isSelected
                    ? 'font-medium text-brand-800 dark:text-brand-300'
                    : 'text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800',
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
