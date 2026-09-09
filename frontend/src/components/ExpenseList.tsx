import { useTranslation } from 'react-i18next'

import type { Expense } from '../types/expense'
import { CategoryBadge } from './CategoryBadge'
import { formatCurrency, formatDate } from '../lib/format'

export function ExpenseList({
  expenses,
  onEdit,
  onDelete,
  onViewReceipt,
}: {
  expenses: Expense[]
  onEdit: (expense: Expense) => void
  onDelete: (expense: Expense) => void
  onViewReceipt: (expense: Expense) => void
}) {
  const { t, i18n } = useTranslation()

  return (
    <div className="overflow-x-auto rounded-2xl border border-stone-200 bg-white shadow-sm dark:border-stone-800 dark:bg-stone-900">
      <table className="min-w-full divide-y divide-stone-200 text-sm dark:divide-stone-800">
        <thead className="bg-stone-50 dark:bg-stone-800/50">
          <tr>
            <th scope="col" className="px-4 py-3 text-left font-medium text-stone-500 dark:text-stone-400">
              {t('expenses.columnBusiness')}
            </th>
            <th scope="col" className="px-4 py-3 text-left font-medium text-stone-500 dark:text-stone-400">
              {t('expenses.columnCategory')}
            </th>
            <th scope="col" className="px-4 py-3 text-left font-medium text-stone-500 dark:text-stone-400">
              {t('expenses.columnDate')}
            </th>
            <th scope="col" className="px-4 py-3 text-right font-medium text-stone-500 dark:text-stone-400">
              {t('expenses.columnAmount')}
            </th>
            <th scope="col" className="px-4 py-3 text-right font-medium text-stone-500 dark:text-stone-400">
              <span className="sr-only">{t('expenses.columnActions')}</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
          {expenses.map((expense) => (
            <tr key={expense.id} className="hover:bg-stone-50 dark:hover:bg-stone-800/50">
              <td className="px-4 py-3">
                <p className="font-medium text-stone-900 dark:text-stone-100">{expense.business_name}</p>
                {expense.receipt_number && (
                  <p className="text-xs text-stone-400 dark:text-stone-500">#{expense.receipt_number}</p>
                )}
              </td>
              <td className="px-4 py-3">
                <CategoryBadge category={expense.category} />
              </td>
              <td className="px-4 py-3 text-stone-600 dark:text-stone-400">{formatDate(expense.expense_date, i18n.language)}</td>
              <td className="px-4 py-3 text-right font-medium tabular-nums text-stone-900 dark:text-stone-100">
                {formatCurrency(expense.amount, expense.currency, i18n.language)}
              </td>
              <td className="px-4 py-3">
                <div className="flex justify-end gap-2">
                  {expense.receipt_image_url && (
                    <button
                      type="button"
                      onClick={() => onViewReceipt(expense)}
                      className="rounded-md px-2 py-1 text-xs font-medium text-stone-600 hover:bg-stone-100 dark:text-stone-400 dark:hover:bg-stone-800"
                      aria-label={t('expenses.viewReceiptAction', { name: expense.business_name })}
                    >
                      {t('expenses.viewReceipt')}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => onEdit(expense)}
                    className="rounded-md px-2 py-1 text-xs font-medium text-brand-700 hover:bg-brand-50 dark:text-brand-400 dark:hover:bg-brand-500/10"
                    aria-label={t('expenses.editAction', { name: expense.business_name })}
                  >
                    {t('common.edit')}
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(expense)}
                    className="rounded-md px-2 py-1 text-xs font-medium text-danger-600 hover:bg-danger-50 dark:text-danger-400 dark:hover:bg-danger-500/10"
                    aria-label={t('expenses.deleteAction', { name: expense.business_name })}
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
