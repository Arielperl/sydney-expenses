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
