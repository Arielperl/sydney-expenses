import { FileText, FileUp, Pencil, Trash2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import type { Sale } from '../types/sale'
import { DocumentStatusBadge } from './DocumentStatusBadge'
import { Money } from './Money'
import { SaleStatusBadge } from './SaleStatusBadge'
import { ServiceBadge } from './ServiceBadge'
import { cardClasses, cx } from './ui-classes'
import { formatCurrency, formatDate } from '../lib/format'

const HEADER = 'px-4 py-2.5 text-xs font-medium text-zinc-500 dark:text-zinc-400'
const ACTION = 'inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-xs font-medium transition-colors'
// Edit/delete repeat on every row, so they stay quiet icons; colour (and red) only appears on hover/focus.
const ICON_ACTION = 'grid h-8 w-8 place-items-center rounded-md text-zinc-500 transition-colors dark:text-zinc-400'

/**
 * One table in the DOM for every screen size: a real table from `md` up, and
 * the same rows restyled as stacked cards on phones (no sideways scrolling).
 */
export function SaleList({
  sales,
  onEdit,
  onDelete,
  onViewDocument,
}: {
  sales: Sale[]
  onEdit: (sale: Sale) => void
  onDelete: (sale: Sale) => void
  onViewDocument: (sale: Sale) => void
}) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()

  return (
    <div className={cx(cardClasses, 'md:overflow-x-auto max-md:border-0 max-md:bg-transparent max-md:shadow-none dark:max-md:bg-transparent')}>
      <table className="w-full text-sm md:min-w-[880px] md:table-fixed max-md:block">
        <colgroup>
          <col className="w-[24%]" />
          <col className="w-[17%]" />
          <col className="w-[16%]" />
          <col className="w-[12%]" />
          <col className="w-[18%]" />
          <col className="w-[13%]" />
        </colgroup>
        <thead className="border-b border-zinc-200 bg-zinc-50/80 max-md:hidden dark:border-zinc-800 dark:bg-zinc-950/30">
          <tr>
            <th scope="col" className={cx(HEADER, 'text-start')}>{t('sales.columnCustomer')}</th>
            <th scope="col" className={cx(HEADER, 'text-start')}>{t('sales.columnService')}</th>
            <th scope="col" className={cx(HEADER, 'text-start')}>{t('sales.columnStatus')}</th>
            <th scope="col" className={cx(HEADER, 'text-start')}>{t('sales.columnDate')}</th>
            <th scope="col" className={cx(HEADER, 'text-end')}>{t('sales.columnAmount')}</th>
            <th scope="col" className={cx(HEADER, 'text-end')}>
              <span className="sr-only">{t('sales.columnActions')}</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100 max-md:block max-md:space-y-3 max-md:divide-y-0 dark:divide-zinc-800">
          {sales.map((sale) => (
            <tr
              key={sale.id}
              onClick={() => navigate(`/sales/${sale.id}`)}
              className={cx(
                'cursor-pointer transition-colors hover:bg-zinc-50/80 dark:hover:bg-zinc-800/40',
                'max-md:grid max-md:grid-cols-[1fr_auto] max-md:gap-x-4 max-md:gap-y-2.5 max-md:rounded-xl max-md:border max-md:border-zinc-200 max-md:bg-white max-md:p-4 max-md:shadow-card dark:max-md:border-zinc-800 dark:max-md:bg-zinc-900',
              )}
            >
              <td className="px-4 py-3.5 text-start align-top max-md:col-start-1 max-md:row-start-1 max-md:p-0">
                <Link
                  to={`/sales/${sale.id}`}
                  onClick={(event) => event.stopPropagation()}
                  className="block truncate font-medium text-zinc-900 hover:text-brand-700 hover:underline underline-offset-2 max-md:whitespace-normal dark:text-zinc-100 dark:hover:text-brand-300"
                  title={sale.customer_name}
                >
                  {sale.customer_name}
                </Link>
                {sale.customer_contact && (
                  <p className="mt-0.5 truncate text-xs text-zinc-500 dark:text-zinc-400" dir="auto">{sale.customer_contact}</p>
                )}
              </td>
              <td className="px-4 py-3.5 text-start align-top max-md:col-span-2 max-md:row-start-2 max-md:p-0">
                <ServiceBadge serviceName={sale.service_name} />
              </td>
              <td className="px-4 py-3.5 text-start align-top max-md:col-span-2 max-md:row-start-3 max-md:p-0">
                <div className="flex flex-col items-start gap-1.5 max-md:flex-row max-md:flex-wrap max-md:items-center">
                  <SaleStatusBadge status={sale.status} />
                  <DocumentStatusBadge status={sale.document_status} />
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">
                    {t(`saleSource.${sale.source}`)}
                  </span>
                </div>
              </td>
              <td className="px-4 py-3.5 text-start align-top whitespace-nowrap text-zinc-600 max-md:col-start-1 max-md:row-start-4 max-md:self-center max-md:p-0 max-md:text-xs dark:text-zinc-400">
                <bdi>{formatDate(sale.occurred_at.slice(0, 10), i18n.language)}</bdi>
              </td>
              <td className="px-4 py-3.5 text-end align-top max-md:col-start-2 max-md:row-start-1 max-md:p-0">
                <span className="font-medium text-zinc-900 dark:text-zinc-50">
                  <Money amount={sale.gross_amount} currency={sale.currency} />
                </span>
                <p className="mt-1 text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
                  {sale.tax_treatment ? (
                    <>
                      <span>
                        {t('sales.vatInline', {
                          amount: formatCurrency(sale.vat_amount ?? 0, sale.currency, i18n.language),
                        })}
                      </span>
                      {' · '}
                      <span>{t(`taxTreatment.${sale.tax_treatment}`)}</span>
                    </>
                  ) : (
                    <span className="font-medium text-amber-800 dark:text-amber-300">{t('sales.taxTreatmentNeedsReview')}</span>
                  )}
                </p>
                {sale.currency !== 'ILS' && (
                  <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                    {t('sales.foreignCurrencyIsraeliTax')}
                  </p>
                )}
              </td>
              <td className="px-4 py-3.5 text-end align-top max-md:col-start-2 max-md:row-start-4 max-md:-my-1 max-md:-me-2 max-md:p-0" onClick={(event) => event.stopPropagation()}>
                <div className="flex flex-wrap items-center justify-end gap-1">
                  {sale.document_url && (
                    <button
                      type="button"
                      onClick={() => onViewDocument(sale)}
                      className={cx(ACTION, 'text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800')}
                      aria-label={t('sales.viewDocumentAction', { name: sale.customer_name })}
                    >
                      <FileText className="h-3.5 w-3.5" aria-hidden="true" />
                      {t('sales.viewDocument')}
                    </button>
                  )}
                  {(sale.document_status === 'pending' || sale.document_status === 'failed') && (
                    <Link
                      to={`/import-document?saleId=${sale.id}`}
                      className={cx(ACTION, 'text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800')}
                    >
                      <FileUp className="h-3.5 w-3.5" aria-hidden="true" />
                      {t('exceptions.importDocument')}
                    </Link>
                  )}
                  <button
                    type="button"
                    onClick={() => onEdit(sale)}
                    className={cx(ICON_ACTION, 'hover:bg-brand-50 hover:text-brand-700 focus-visible:text-brand-700 dark:hover:bg-brand-500/10 dark:hover:text-brand-300')}
                    aria-label={t('sales.editAction', { name: sale.customer_name })}
                    title={t('common.edit')}
                  >
                    <Pencil className="h-4 w-4" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(sale)}
                    className={cx(ICON_ACTION, 'hover:bg-danger-50 hover:text-danger-700 focus-visible:text-danger-700 dark:hover:bg-danger-500/10 dark:hover:text-danger-500')}
                    aria-label={t('sales.deleteAction', { name: sale.customer_name })}
                    title={t('common.delete')}
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
