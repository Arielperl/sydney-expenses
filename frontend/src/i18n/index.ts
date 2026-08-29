import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import en from './locales/en/translation.json'
import he from './locales/he/translation.json'

export const SUPPORTED_LANGUAGES = ['he', 'en'] as const
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number]

export const DEFAULT_LANGUAGE: SupportedLanguage = 'he'
export const LANGUAGE_STORAGE_KEY = 'receiptly-language'

const RTL_LANGUAGES: SupportedLanguage[] = ['he']

export function directionForLanguage(language: string): 'rtl' | 'ltr' {
  return RTL_LANGUAGES.includes(language as SupportedLanguage) ? 'rtl' : 'ltr'
}

function readStoredLanguage(): SupportedLanguage {
  try {
    const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY)
    if (stored && (SUPPORTED_LANGUAGES as readonly string[]).includes(stored)) {
      return stored as SupportedLanguage
    }
  } catch {
    // localStorage unavailable (private browsing, disabled storage) — fall back to default.
  }
  return DEFAULT_LANGUAGE
}

export function applyDocumentDirection(language: string): void {
  document.documentElement.lang = language
  document.documentElement.dir = directionForLanguage(language)
}

const initialLanguage = readStoredLanguage()

void i18n
  .use(initReactI18next)
  .init({
    resources: {
      he: { translation: he },
      en: { translation: en },
    },
    lng: initialLanguage,
    fallbackLng: DEFAULT_LANGUAGE,
    interpolation: { escapeValue: false },
    returnEmptyString: false,
  })

applyDocumentDirection(initialLanguage)

i18n.on('languageChanged', (language) => {
  applyDocumentDirection(language)
  try {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language)
  } catch {
    // Ignore storage failures — the language still applies for this session.
  }
})

export default i18n
