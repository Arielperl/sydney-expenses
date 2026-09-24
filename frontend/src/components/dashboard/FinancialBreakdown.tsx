import { useTranslation } from 'react-i18next'

import type { CurrencyAmount } from '../../types/dashboard'
import { Money } from '../Money'
import { Card, CardHeader } from '../ui'
import { cx } from '../ui-classes'

function currenciesOf(rows: CurrencyAmount[][]): string[] {
  const set = new Set<string>()
  for (const list of rows) {
    for (const row of list) set.add(row.currency)
  }
  return Array.from(set).sort((a, b) => Number(b === 'ILS') - Number(a === 'ILS') || a.localeCompare(b))
}

function amountFor(rows: CurrencyAmount[], currency: string): number | string {
  return rows.find((row) => row.currency === currency)?.amount ?? 0
}

/**
 * Explains what the net figure is made of. Deliberately NOT drawn as a
 * subtraction: `refunds_total` also covers fully refunded sales, which are
 * already excluded from gross, so "gross − VAT − fees − refunds" would not
 * equal net whenever a full refund exists. Each component is defined instead.
 */
export function FinancialBreakdown({
  grossRevenue,
  vatCollected,
  processingFees,
  refundsTotal,
  netRevenue,
  className,
}: {
  grossRevenue: CurrencyAmount[]
  vatCollected: CurrencyAmount[]
  processingFees: CurrencyAmount[]
  refundsTotal: CurrencyAmount[]
  netRevenue: CurrencyAmount[]
  className?: string
}) {
  const { t } = useTranslation()
  const currencies = currenciesOf([grossRevenue, vatCollected, processingFees, refundsTotal, netRevenue])
  if (currencies.length === 0) currencies.push('ILS')

  const rows: { key: string; label: string; hint: string; values: CurrencyAmount[]; total?: boolean }[] = [
    { key: 'gross', label: t('dashboard.breakdown.gross'), hint: t('dashboard.breakdown.grossHint'), values: grossRevenue },
    { key: 'vat', label: t('dashboard.breakdown.vat'), hint: t('dashboard.breakdown.vatHint'), values: vatCollected },
    { key: 'fees', label: t('dashboard.breakdown.fees'), hint: t('dashboard.breakdown.feesHint'), values: processingFees },
    { key: 'refunds', label: t('dashboard.breakdown.refunds'), hint: t('dashboard.breakdown.refundsHint'), values: refundsTotal },
    { key: 'net', label: t('dashboard.breakdown.net'), hint: t('dashboard.breakdown.netHint'), values: netRevenue, total: true },
  ]

  return (
    <Card className={className} aria-labelledby="breakdown-title">
      <CardHeader id="breakdown-title" title={t('dashboard.breakdown.title')} description={t('dashboard.breakdown.description')} />
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[520px] text-sm">
          <thead>
            <tr className="border-y border-zinc-100 bg-zinc-50/70 text-xs text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950/30 dark:text-zinc-400">
              <th scope="col" className="px-5 py-2 text-start font-medium">{t('dashboard.breakdown.metric')}</th>
              {currencies.map((currency) => (
                <th key={currency} scope="col" className="px-5 py-2 text-end font-medium tracking-wider">{currency}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {rows.map((row) => (
              <tr key={row.key} className={cx(row.total && 'bg-brand-50/50 dark:bg-brand-500/5')}>
                <th scope="row" className="px-5 py-3 text-start align-top font-normal">
                  <span className={cx('text-zinc-900 dark:text-zinc-100', row.total ? 'font-semibold' : 'font-medium')}>{row.label}</span>
                  <p className="mt-0.5 max-w-md text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">{row.hint}</p>
                </th>
                {currencies.map((currency) => (
                  <td key={currency} className={cx('px-5 py-3 text-end align-top whitespace-nowrap text-zinc-900 dark:text-zinc-100', row.total ? 'font-semibold' : 'font-normal')}>
                    <Money amount={amountFor(row.values, currency)} currency={currency} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="space-y-1 border-t border-zinc-100 px-5 py-3.5 text-xs leading-relaxed text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
        <p>{t('dashboard.breakdown.reconcileNote')}</p>
        <p>{t('dashboard.breakdown.notProfitNote')}</p>
      </div>
    </Card>
  )
}
