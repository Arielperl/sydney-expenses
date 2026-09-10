import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { formatCurrency, formatDate } from '../lib/format'
import { toApiError } from '../services/apiClient'
import { confirmCsvImport, previewCsv } from '../services/importService'
import type { CsvConfirmResponse, CsvPreviewResponse } from '../types/imports'

type WizardState = 'idle' | 'previewing' | 'previewed' | 'confirming' | 'summary'

export function CsvImportWizard() {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const [state, setState] = useState<WizardState>('idle')
  const [preview, setPreview] = useState<CsvPreviewResponse | null>(null)
  const [summary, setSummary] = useState<CsvConfirmResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleFileSelected(file: File) {
    setState('previewing')
    setError(null)
    try {
      const result = await previewCsv(file)
      setPreview(result)
      setState('previewed')
    } catch (err) {
      setError(toApiError(err).message)
      setState('idle')
    }
  }

  async function handleConfirm() {
    if (!preview) return
    setState('confirming')
    setError(null)
    try {
      const result = await confirmCsvImport(preview.file_hash, preview.filename, preview.valid_rows)
      setSummary(result)
      setState('summary')
      queryClient.invalidateQueries({ queryKey: ['expenses'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      queryClient.invalidateQueries({ queryKey: ['reconciliation-inbox'] })
    } catch (err) {
      setError(toApiError(err).message)
      setState('previewed')
    }
  }

  function handleReset() {
    setState('idle')
    setPreview(null)
    setSummary(null)
    setError(null)
  }

  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm dark:border-stone-800 dark:bg-stone-900">
      <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">{t('imports.csv.heading')}</h2>
      <p className="mt-1 text-xs text-stone-500 dark:text-stone-400">{t('imports.csv.formatNote')}</p>

      {(state === 'idle' || state === 'previewing') && (
        <div className="mt-4">
          <input
            type="file"
            accept=".csv,text/csv"
            aria-label={t('imports.csv.chooseFile')}
            disabled={state === 'previewing'}
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) void handleFileSelected(file)
            }}
            className="block w-full text-sm text-stone-600 file:me-4 file:rounded-md file:border-0 file:bg-brand-600 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-brand-700 dark:text-stone-300"
          />
          {state === 'previewing' && (
            <p role="status" className="mt-2 text-sm text-stone-500 dark:text-stone-400">
              {t('imports.csv.uploading')}
            </p>
          )}
        </div>
      )}

      {error && (
        <p role="alert" className="mt-3 text-sm text-danger-600 dark:text-danger-400">
          {error}
        </p>
      )}

      {state === 'previewed' && preview && (
        <div className="mt-4">
          <h3 className="text-sm font-semibold text-stone-900 dark:text-stone-100">{t('imports.csv.previewHeading')}</h3>
          <p className="mt-1 text-sm text-stone-600 dark:text-stone-400">
            {t('imports.csv.validRows', { count: preview.valid_rows.length })}
            {preview.errors.length > 0 && ` · ${t('imports.csv.errorRows', { count: preview.errors.length })}`}
          </p>
          {preview.is_repeat_file && (
            <p className="mt-2 rounded-lg border border-amber-400/40 bg-amber-50 p-2 text-xs text-amber-800 dark:bg-amber-500/10 dark:text-amber-300">
              {t('imports.csv.repeatFileWarning')}
            </p>
          )}

          {preview.valid_rows.length > 0 && (
            <div className="mt-3 overflow-x-auto rounded-lg border border-stone-200 dark:border-stone-800">
              <table className="min-w-full divide-y divide-stone-200 text-sm dark:divide-stone-800">
                <thead className="bg-stone-50 dark:bg-stone-800/50">
                  <tr>
                    <th scope="col" className="px-3 py-2 text-start font-medium text-stone-500 dark:text-stone-400">
                      {t('imports.csv.columnDate')}
                    </th>
                    <th scope="col" className="px-3 py-2 text-start font-medium text-stone-500 dark:text-stone-400">
                      {t('imports.csv.columnMerchant')}
                    </th>
                    <th scope="col" className="px-3 py-2 text-end font-medium text-stone-500 dark:text-stone-400">
                      {t('imports.csv.columnAmount')}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
                  {preview.valid_rows.map((row) => (
                    <tr key={row.row_number}>
                      <td className="px-3 py-2 text-stone-600 dark:text-stone-400">
                        {formatDate(row.expense_date, i18n.language)}
                      </td>
                      <td className="px-3 py-2 text-stone-900 dark:text-stone-100">{row.merchant}</td>
                      <td className="px-3 py-2 text-end tabular-nums text-stone-900 dark:text-stone-100">
                        {formatCurrency(row.amount, row.currency, i18n.language)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {preview.errors.length > 0 && (
            <div className="mt-3 overflow-x-auto rounded-lg border border-danger-500/30">
              <table className="min-w-full divide-y divide-stone-200 text-sm dark:divide-stone-800">
                <thead className="bg-danger-50 dark:bg-danger-500/10">
                  <tr>
                    <th scope="col" className="px-3 py-2 text-start font-medium text-danger-700 dark:text-danger-400">
                      {t('imports.csv.columnRow')}
                    </th>
                    <th scope="col" className="px-3 py-2 text-start font-medium text-danger-700 dark:text-danger-400">
                      {t('imports.csv.columnError')}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
                  {preview.errors.map((rowError) => (
                    <tr key={rowError.row_number}>
                      <td className="px-3 py-2 text-stone-600 dark:text-stone-400">{rowError.row_number}</td>
                      <td className="px-3 py-2 text-danger-700 dark:text-danger-400">{rowError.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={handleReset}
              className="rounded-md border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:text-stone-200 dark:hover:bg-stone-800"
            >
              {t('imports.csv.startOver')}
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={preview.valid_rows.length === 0}
              className="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {t('imports.csv.confirmImport')}
            </button>
          </div>
        </div>
      )}

      {state === 'confirming' && (
        <p role="status" className="mt-4 text-sm text-stone-500 dark:text-stone-400">
          {t('imports.csv.confirming')}
        </p>
      )}

      {state === 'summary' && summary && (
        <div className="mt-4 rounded-lg border border-success-500/30 bg-success-50 p-4 dark:bg-success-500/10">
          <p className="font-semibold text-success-700 dark:text-success-400">{t('imports.csv.summaryTitle')}</p>
          <p className="mt-1 text-sm text-success-700 dark:text-success-400">
            {t('imports.csv.summaryCreated', { count: summary.created_count })}
          </p>
          {summary.duplicate_count > 0 && (
            <p className="text-sm text-success-700 dark:text-success-400">
              {t('imports.csv.summaryDuplicate', { count: summary.duplicate_count })}
            </p>
          )}
          <button
            type="button"
            onClick={handleReset}
            className="mt-3 rounded-md border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:text-stone-200 dark:hover:bg-stone-800"
          >
            {t('imports.csv.startOver')}
          </button>
        </div>
      )}
    </div>
  )
}
