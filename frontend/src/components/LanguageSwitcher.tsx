import { useTranslation } from 'react-i18next'

import { SUPPORTED_LANGUAGES, type SupportedLanguage } from '../i18n'

const LABEL_KEY: Record<SupportedLanguage, 'hebrew' | 'english'> = {
  he: 'hebrew',
  en: 'english',
}

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation()
  const currentLanguage = i18n.language as SupportedLanguage

  return (
    <div role="group" aria-label={t('language.switcherLabel')} className="flex overflow-hidden rounded-md border border-slate-300">
      {SUPPORTED_LANGUAGES.map((language) => (
        <button
          key={language}
          type="button"
          data-testid={`language-switch-${language}`}
          onClick={() => i18n.changeLanguage(language)}
          aria-pressed={currentLanguage === language}
          className={[
            'px-3 py-1.5 text-sm font-medium transition-colors',
            currentLanguage === language
              ? 'bg-brand-600 text-white'
              : 'bg-white text-slate-600 hover:bg-slate-100',
          ].join(' ')}
        >
          {t(`language.${LABEL_KEY[language]}`)}
        </button>
      ))}
    </div>
  )
}
