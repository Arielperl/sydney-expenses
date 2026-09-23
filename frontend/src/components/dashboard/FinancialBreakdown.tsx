import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { formatCurrency } from '../../lib/format'
import type { CurrencyAmount } from '../../types/dashboard'

function currenciesOf(rows: CurrencyAmount[][]): string[] {
  const set = new Set<string>()
  for (const list of rows) {
    for (const row of list) set.add(row.currency)
  }
  return Array.from(set).sort()
}

function amountFor(rows: CurrencyAmount[], currency: string): number | string {
  return rows.find((row) => row.currency === currency)?.amount ?? 0
}

/** Lower visual priority than the primary card and chart on purpose — VAT,
 * fees, and refunds are context for the net-revenue figure, not the
 * headline. Collapsible so it takes almost no space until asked for. */
export function FinancialBreakdown({
  grossRevenue,
  vatCollected,
  processingFees,
  refundsTotal,
  netRevenue,
}: {
  grossRevenue: CurrencyAmount[]
  vatCollected: CurrencyAmount[]
  processingFees: CurrencyAmount[]
  refundsTotal: CurrencyAmount[]
  netRevenue: CurrencyAmount[]
}) {
  const { t, i18n } = useTranslation()
  const [isOpen, setIsOpen] = useState(false)
  const currencies = currenciesOf([grossRevenue, vatCollected, processingFees, refundsTotal, netRevenue])
  if (currencies.length === 0) currencies.push('ILS')

  const rows: { key: string; label: string; hint: string; values: CurrencyAmount[] }[] = [
    { key: 'gross', label: t('dashboard.breakdown.gross'), hint: t('dashboard.breakdown.grossHint'), values: grossRevenue },
    { key: 'vat', label: t('dashboard.breakdown.vat'), hint: t('dashboard.breakdown.vatHint'), values: vatCollected },
    { key: 'fees', label: t('dashboard.breakdown.fees'), hint: t('dashboard.breakdown.feesHint'), values: processingFees },
    { key: 'refunds', label: t('dashboard.breakdown.refunds'), hint: t('dashboard.breakdown.refundsHint'), values: refundsTotal },
    { key: 'net', label: t('dashboard.breakdown.net'), hint: t('dashboard.breakdown.netHint'), values: netRevenue },
  ]

  return (
    <div className="rounded-xl border border-zinc-200 bg-zinc-50/60 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/40">
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-expanded={isOpen}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-start"
      >
        <span className="text-sm font-semibold text-zinc-700 dark:text-zinc-200">{t('dashboard.breakdown.title')}</span>
        <span className="text-zinc-400 transition-transform" style={{ transform: isOpen ? 'rotate(180deg)' : undefined }} aria-hidden="true">
          ▾
        </span>
      </button>

      {isOpen && (
        <div className="overflow-x-auto border-t border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <table className="w-full min-w-[420px] text-sm">
            <thead>
              <tr className="text-xs text-zinc-400 dark:text-zinc-500">
                <th scope="col" className="py-1 text-start font-medium">
                  {t('dashboard.breakdown.metric')}
                </th>
                {currencies.map((currency) => (
                  <th key={currency} scope="col" className="py-1 text-end font-medium">
                    {currency}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {rows.map((row) => (
                <tr key={row.key}>
                  <td className="py-2 pe-4 align-top">
                    <span className="font-medium text-zinc-700 dark:text-zinc-200">{row.label}</span>
                    <p className="mt-0.5 text-xs text-zinc-400 dark:text-zinc-500">{row.hint}</p>
                  </td>
                  {currencies.map((currency) => (
                    <td key={currency} className="py-2 text-end align-top font-medium tabular-nums text-zinc-900 dark:text-zinc-100">
                      {formatCurrency(amountFor(row.values, currency), currency, i18n.language)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs text-zinc-400 dark:text-zinc-500">{t('dashboard.breakdown.notProfitNote')}</p>
        </div>
      )}
    </div>
  )
}
