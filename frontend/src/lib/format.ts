const INTL_LOCALE_BY_LANGUAGE: Record<string, string> = {
  he: 'he-IL',
  en: 'en-US',
}

export function intlLocale(language: string): string {
  return INTL_LOCALE_BY_LANGUAGE[language] ?? 'en-US'
}

export function formatCurrency(amount: number | string, currency: string, language: string): string {
  const numericAmount = typeof amount === 'string' ? Number(amount) : amount
  const locale = intlLocale(language)
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      currencyDisplay: 'symbol',
    }).format(numericAmount)
  } catch {
    return `${numericAmount.toFixed(2)} ${currency}`
  }
}

export function formatDate(isoDate: string, language: string): string {
  const date = new Date(`${isoDate}T00:00:00`)
  return new Intl.DateTimeFormat(intlLocale(language), { year: 'numeric', month: 'short', day: 'numeric' }).format(
    date,
  )
}

export function formatDateTime(isoDateTime: string, language: string): string {
  const date = new Date(isoDateTime)
  return new Intl.DateTimeFormat(intlLocale(language), {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function todayIsoDate(): string {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}
