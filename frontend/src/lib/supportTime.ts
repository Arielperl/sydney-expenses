import { intlLocale } from './format'

/**
 * Support timestamps are stored as naive UTC (`datetime.utcnow()`) and arrive
 * without a zone designator. `new Date()` would read those as local time, so
 * anything without an explicit offset is treated as UTC here.
 */
export function parseServerTimestamp(value: string): Date {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value)
  return new Date(hasZone ? value : `${value}Z`)
}

const RELATIVE_STEPS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['minute', 60],
  ['hour', 60 * 60],
  ['day', 60 * 60 * 24],
]

/** "5 minutes ago", "yesterday"; falls back to a calendar date after a week. */
export function formatRelativeTime(date: Date, language: string, now: Date = new Date()): string {
  const seconds = Math.round((date.getTime() - now.getTime()) / 1000)
  const absolute = Math.abs(seconds)
  const locale = intlLocale(language)
  if (absolute < 45) return new Intl.RelativeTimeFormat(locale, { numeric: 'auto' }).format(0, 'second')
  if (absolute < 60 * 60 * 24 * 7) {
    const [unit, size] = [...RELATIVE_STEPS].reverse().find(([, step]) => absolute >= step) ?? RELATIVE_STEPS[0]
    return new Intl.RelativeTimeFormat(locale, { numeric: 'auto' }).format(Math.round(seconds / size), unit)
  }
  return formatDay(date, language, now)
}

export function formatFullTimestamp(date: Date, language: string): string {
  return new Intl.DateTimeFormat(intlLocale(language), { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

export function formatClockTime(date: Date, language: string): string {
  return new Intl.DateTimeFormat(intlLocale(language), { hour: '2-digit', minute: '2-digit' }).format(date)
}

/** A calendar date, omitting the year when it is the current one. */
export function formatDay(date: Date, language: string, now: Date = new Date()): string {
  return new Intl.DateTimeFormat(intlLocale(language), {
    day: 'numeric',
    month: 'long',
    ...(date.getFullYear() === now.getFullYear() ? {} : { year: 'numeric' }),
  }).format(date)
}

export function localDayKey(date: Date): string {
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`
}
