import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { formatCurrency, todayIsoDate } from '../format'

describe('todayIsoDate', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns the local Israel-timezone date, not a UTC-shifted date', () => {
    // 2026-08-30T23:30:00 in Asia/Jerusalem (UTC+3) is still 2026-08-30 locally,
    // even though it is already 2026-08-30T20:30:00Z / into the next UTC day boundary
    // territory that a naive toISOString()-based implementation would get wrong.
    vi.setSystemTime(new Date('2026-08-30T23:30:00+03:00'))

    expect(todayIsoDate()).toBe('2026-08-30')
  })

  it('does not roll back a day right after local midnight', () => {
    // 00:30 local time in Jerusalem is 21:30 UTC the *previous* day — a UTC-based
    // implementation (toISOString().slice(0, 10)) would incorrectly report the
    // previous date here.
    vi.setSystemTime(new Date('2026-08-30T00:30:00+03:00'))

    expect(todayIsoDate()).toBe('2026-08-30')
  })
})

describe('formatCurrency', () => {
  it('formats a decimal string amount for the Hebrew locale', () => {
    const result = formatCurrency('184.90', 'ILS', 'he')
    expect(result).toContain('184.90')
    expect(result).toContain('₪')
  })

  it('formats a numeric amount for the English locale', () => {
    const result = formatCurrency(184.9, 'ILS', 'en')
    expect(result).toContain('184.90')
  })
})
