import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import type { Sale } from '../types/sale'
import { DocumentStatusBadge } from './DocumentStatusBadge'
import { SaleStatusBadge } from './SaleStatusBadge'
import { ServiceBadge } from './ServiceBadge'
import { formatCurrency, formatDate } from '../lib/format'

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
    <div className="overflow-x-auto rounded-2xl border border-stone-200 bg-white shadow-sm dark:border-stone-800 dark:bg-stone-900">
      <table className="w-full min-w-[900px] table-fixed divide-y divide-stone-200 text-sm dark:divide-stone-800">
        <colgroup>
          <col className="w-[24%]" />
          <col className="w-[16%]" />
          <col className="w-[18%]" />
          <col className="w-[12%]" />
          <col className="w-[12%]" />
          <col className="w-[18%]" />
        </colgroup>
        <thead className="bg-stone-50 dark:bg-stone-800/50">
          <tr>
            <th scope="col" className="px-4 py-3 text-start font-medium text-stone-500 dark:text-stone-400">
              {t('sales.columnCustomer')}
            </th>
            <th scope="col" className="px-4 py-3 text-start font-medium text-stone-500 dark:text-stone-400">
              {t('sales.columnService')}
            </th>
            <th scope="col" className="px-4 py-3 text-start font-medium text-stone-500 dark:text-stone-400">
              {t('sales.columnStatus')}
            </th>
            <th scope="col" className="px-4 py-3 text-start font-medium text-stone-500 dark:text-stone-400">
              {t('sales.columnDate')}
            </th>
            <th scope="col" className="px-4 py-3 text-end font-medium text-stone-500 dark:text-stone-400">
              {t('sales.columnAmount')}
            </th>
            <th scope="col" className="px-4 py-3 text-end font-medium text-stone-500 dark:text-stone-400">
              <span className="sr-only">{t('sales.columnActions')}</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
          {sales.map((sale) => (
            <tr
              key={sale.id}
              onClick={() => navigate(`/sales/${sale.id}`)}
              className="cursor-pointer hover:bg-stone-50 dark:hover:bg-stone-800/50"
            >
              <td className="px-4 py-3 text-start align-top">
                <Link
                  to={`/sales/${sale.id}`}
                  onClick={(event) => event.stopPropagation()}
                  className="truncate font-medium text-stone-900 hover:text-brand-600 hover:underline dark:text-stone-100 dark:hover:text-brand-400"
                >
                  {sale.customer_name}
                </Link>
                {sale.customer_contact && (
                  <p className="truncate text-xs text-stone-400 dark:text-stone-500">{sale.customer_contact}</p>
                )}
              </td>
              <td className="px-4 py-3 text-start align-top">
                <ServiceBadge serviceName={sale.service_name} />
              </td>
              <td className="px-4 py-3 text-start align-top">
                <div className="flex flex-col items-start gap-1">
                  <SaleStatusBadge status={sale.status} />
                  <DocumentStatusBadge status={sale.document_status} />
                  <span className="text-xs text-stone-400 dark:text-stone-500">
                    {t(`saleSource.${sale.source}`)}
                  </span>
                </div>
              </td>
              <td className="px-4 py-3 text-start align-top text-stone-600 dark:text-stone-400">
                {formatDate(sale.occurred_at.slice(0, 10), i18n.language)}
              </td>
              <td className="px-4 py-3 text-end align-top font-medium tabular-nums text-stone-900 dark:text-stone-100">
                {formatCurrency(sale.gross_amount, sale.currency, i18n.language)}
                <p className="mt-0.5 text-xs font-normal text-stone-400 dark:text-stone-500">
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
                    <span>{t('sales.taxTreatmentNeedsReview')}</span>
                  )}
                </p>
                {sale.currency !== 'ILS' && (
                  <p className="mt-0.5 text-xs font-normal text-stone-400 dark:text-stone-500">
                    {t('sales.foreignCurrencyIsraeliTax')}
                  </p>
                )}
              </td>
              <td className="px-4 py-3 text-end align-top" onClick={(event) => event.stopPropagation()}>
                <div className="flex flex-wrap justify-end gap-2">
                  {sale.document_url && (
                    <button
                      type="button"
                      onClick={() => onViewDocument(sale)}
                      className="rounded-md px-2 py-1 text-xs font-medium text-stone-600 hover:bg-stone-100 dark:text-stone-400 dark:hover:bg-stone-800"
                      aria-label={t('sales.viewDocumentAction', { name: sale.customer_name })}
                    >
                      {t('sales.viewDocument')}
                    </button>
                  )}
                  {(sale.document_status === 'pending' || sale.document_status === 'failed') && (
                    <Link
                      to={`/import-document?saleId=${sale.id}`}
                      className="rounded-md px-2 py-1 text-xs font-medium text-stone-600 hover:bg-stone-100 dark:text-stone-400 dark:hover:bg-stone-800"
                    >
                      {t('exceptions.importDocument')}
                    </Link>
                  )}
                  <button
                    type="button"
                    onClick={() => onEdit(sale)}
                    className="rounded-md px-2 py-1 text-xs font-medium text-brand-700 hover:bg-brand-50 dark:text-brand-400 dark:hover:bg-brand-500/10"
                    aria-label={t('sales.editAction', { name: sale.customer_name })}
                  >
                    {t('common.edit')}
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(sale)}
                    className="rounded-md px-2 py-1 text-xs font-medium text-danger-600 hover:bg-danger-50 dark:text-danger-400 dark:hover:bg-danger-500/10"
                    aria-label={t('sales.deleteAction', { name: sale.customer_name })}
                  >
                    {t('common.delete')}
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
