import { useTranslation } from 'react-i18next'

import type { Expense } from '../types/expense'
import { CategoryBadge } from './CategoryBadge'
import { formatCurrency, formatDate } from '../lib/format'

export function ExpenseList({
  expenses,
  onEdit,
  onDelete,
}: {
  expenses: Expense[]
  onEdit: (expense: Expense) => void
  onDelete: (expense: Expense) => void
}) {
  const { t, i18n } = useTranslation()

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50">
          <tr>
            <th scope="col" className="px-4 py-3 text-left font-medium text-slate-500">
              {t('expenses.columnBusiness')}
            </th>
            <th scope="col" className="px-4 py-3 text-left font-medium text-slate-500">
              {t('expenses.columnCategory')}
            </th>
            <th scope="col" className="px-4 py-3 text-left font-medium text-slate-500">
              {t('expenses.columnDate')}
            </th>
            <th scope="col" className="px-4 py-3 text-right font-medium text-slate-500">
              {t('expenses.columnAmount')}
            </th>
            <th scope="col" className="px-4 py-3 text-right font-medium text-slate-500">
              <span className="sr-only">{t('expenses.columnActions')}</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {expenses.map((expense) => (
            <tr key={expense.id} className="hover:bg-slate-50">
              <td className="px-4 py-3">
                <p className="font-medium text-slate-900">{expense.business_name}</p>
                {expense.receipt_number && (
                  <p className="text-xs text-slate-400">#{expense.receipt_number}</p>
                )}
              </td>
              <td className="px-4 py-3">
                <CategoryBadge category={expense.category} />
              </td>
              <td className="px-4 py-3 text-slate-600">{formatDate(expense.expense_date, i18n.language)}</td>
              <td className="px-4 py-3 text-right font-medium text-slate-900">
                {formatCurrency(expense.amount, expense.currency, i18n.language)}
              </td>
              <td className="px-4 py-3">
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => onEdit(expense)}
                    className="rounded-md px-2 py-1 text-xs font-medium text-brand-700 hover:bg-brand-50"
                    aria-label={t('expenses.editAction', { name: expense.business_name })}
                  >
                    {t('common.edit')}
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(expense)}
                    className="rounded-md px-2 py-1 text-xs font-medium text-danger-600 hover:bg-danger-50"
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
