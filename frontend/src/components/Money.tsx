import { useTranslation } from 'react-i18next'

import { useAnimatedNumber } from '../hooks/useAnimatedNumber'
import { formatCurrency, intlLocale } from '../lib/format'
import { cx } from './ui-classes'

/**
 * A single currency amount, formatted with Intl for the active language.
 * Wrapped in <bdi> so "₪1,250.00" never reorders inside Hebrew sentences,
 * and rendered with tabular figures so columns of amounts align.
 */
export function Money({
  amount,
  currency,
  animate = false,
  className,
}: {
  amount: number | string
  currency: string
  animate?: boolean
  className?: string
}) {
  const { i18n } = useTranslation()
  const numeric = typeof amount === 'string' ? Number(amount) : amount
  const shown = useAnimatedNumber(animate ? numeric : Number.NaN)
  const display = animate && Number.isFinite(shown) ? shown : numeric
  return <bdi className={cx('figure', className)}>{formatCurrency(display, currency, i18n.language)}</bdi>
}

export function Count({ value, className }: { value: number; className?: string }) {
  const { i18n } = useTranslation()
  const shown = useAnimatedNumber(value)
  return <bdi className={cx('figure', className)}>{new Intl.NumberFormat(intlLocale(i18n.language)).format(Math.round(shown))}</bdi>
}
