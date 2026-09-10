import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { FormField, inputClasses } from '../components/FormField'
import { Modal } from '../components/Modal'
import { EmptyState, ErrorState, LoadingState } from '../components/StatusStates'
import { toApiError } from '../services/apiClient'
import { getDemoResetPreview, resetDemoData, simulateDemoSale } from '../services/demoService'
import { getSystemCapabilities } from '../services/systemService'
import { DEMO_SCENARIOS, type DemoScenario } from '../types/demo'
import { PAYMENT_METHODS, TAX_TREATMENTS, TRANSACTION_CURRENCIES, type PaymentMethod, type TaxTreatment, type TransactionCurrency } from '../types/sale'

// Realistic Hebrew demo names — quick-pick suggestions, never a literal
// "DEMO" string in the name itself (the sale is labeled as demo data via
// its source, not by polluting the customer/service name).
const DEMO_CUSTOMER_NAMES = ['דנה כהן', 'משה לוי', 'נועה מזרחי', 'אבי פרידמן', 'שירה בן־דוד']
const DEMO_SERVICE_NAMES = ['ייעוץ עסקי', 'עיצוב אתרים', 'ליווי שיווקי', 'פיתוח תוכנה', 'הדרכה ארגונית']

const DEFAULT_FORM = {
  customer_name: '',
  customer_contact: '',
  service_name: '',
  gross_amount: '118.00',
  currency: 'ILS' as TransactionCurrency,
  payment_method: 'card' as PaymentMethod,
  tax_treatment: 'standard' as TaxTreatment,
  scenario: 'succeeded' as DemoScenario,
}

export function DemoSimulatorPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [form, setForm] = useState(DEFAULT_FORM)
  const [isResetDialogOpen, setIsResetDialogOpen] = useState(false)
  const [resetSummary, setResetSummary] = useState<string | null>(null)

  const { data: capabilities, isLoading: isLoadingCapabilities } = useQuery({
    queryKey: ['system-capabilities'],
    queryFn: getSystemCapabilities,
  })

  const simulateMutation = useMutation({
    mutationFn: () =>
      simulateDemoSale({
        customer_name: form.customer_name.trim(),
        customer_contact: form.customer_contact.trim() || null,
        service_name: form.service_name.trim(),
        gross_amount: Number(form.gross_amount),
        currency: form.currency,
        payment_method: form.payment_method || null,
        tax_treatment: form.tax_treatment,
        scenario: form.scenario,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sales'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })

  const resetPreviewQuery = useQuery({
    queryKey: ['demo-reset-preview'],
    queryFn: getDemoResetPreview,
    enabled: isResetDialogOpen,
  })

  const resetMutation = useMutation({
    mutationFn: resetDemoData,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['sales'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      setIsResetDialogOpen(false)
      setResetSummary(t('demo.reset.successSummary', { count: result.deleted_sales_count }))
    },
  })

  if (isLoadingCapabilities) return <LoadingState label={t('common.loading')} />

  if (!capabilities?.demo_simulator_enabled) {
    return (
      <div className="max-w-2xl">
        <EmptyState
          title={t('demo.disabledTitle')}
          description={t('demo.disabledDescription')}
        />
      </div>
    )
  }

  function guardedSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (simulateMutation.isPending) return
    simulateMutation.mutate()
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">{t('demo.title')}</h1>
          <span className="inline-flex items-center rounded-full bg-accent-500/10 px-2.5 py-0.5 text-xs font-semibold text-accent-700 dark:text-accent-400">
            {t('demo.badge')}
          </span>
        </div>
        <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('demo.subtitle')}</p>
      </div>

      <form
        onSubmit={guardedSubmit}
        className="space-y-5 rounded-2xl border border-stone-200 bg-white p-6 shadow-sm dark:border-stone-800 dark:bg-stone-900"
      >
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <FormField label={t('form.customerName')} htmlFor="demo_customer_name" required>
            <input
              id="demo_customer_name"
              className={inputClasses}
              placeholder={t('form.customerNamePlaceholder')}
              value={form.customer_name}
              onChange={(event) => setForm({ ...form, customer_name: event.target.value })}
              list="demo-customer-names"
              required
            />
            <datalist id="demo-customer-names">
              {DEMO_CUSTOMER_NAMES.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </FormField>

          <FormField label={t('form.customerContact')} htmlFor="demo_customer_contact" hint={t('form.customerContactHint')}>
            <input
              id="demo_customer_contact"
              className={inputClasses}
              placeholder={t('form.customerContactPlaceholder')}
              value={form.customer_contact}
              onChange={(event) => setForm({ ...form, customer_contact: event.target.value })}
            />
          </FormField>

          <FormField label={t('form.serviceName')} htmlFor="demo_service_name" required>
            <input
              id="demo_service_name"
              className={inputClasses}
              placeholder={t('form.serviceNamePlaceholder')}
              value={form.service_name}
              onChange={(event) => setForm({ ...form, service_name: event.target.value })}
              list="demo-service-names"
              required
            />
            <datalist id="demo-service-names">
              {DEMO_SERVICE_NAMES.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </FormField>

          <FormField label={t('form.grossAmount')} htmlFor="demo_gross_amount" required>
            <input
              id="demo_gross_amount"
              type="number"
              step="0.01"
              min="0.01"
              className={inputClasses}
              value={form.gross_amount}
              onChange={(event) => setForm({ ...form, gross_amount: event.target.value })}
              required
            />
          </FormField>

          <FormField label={t('form.currency')} htmlFor="demo_currency" required>
            <select
              id="demo_currency"
              className={inputClasses}
              value={form.currency}
              onChange={(event) => setForm({ ...form, currency: event.target.value as TransactionCurrency })}
            >
              {TRANSACTION_CURRENCIES.map((code) => (
                <option key={code} value={code}>
                  {t(`currency.${code}`)}
                </option>
              ))}
            </select>
          </FormField>

          <FormField label={t('form.paymentMethod')} htmlFor="demo_payment_method">
            <select
              id="demo_payment_method"
              className={inputClasses}
              value={form.payment_method}
              onChange={(event) => setForm({ ...form, payment_method: event.target.value as PaymentMethod })}
            >
              {PAYMENT_METHODS.map((method) => (
                <option key={method} value={method}>
                  {t(`paymentMethod.${method}`)}
                </option>
              ))}
            </select>
          </FormField>

          <FormField label={t('form.taxTreatment')} htmlFor="demo_tax_treatment" required>
            <select
              id="demo_tax_treatment"
              className={inputClasses}
              value={form.tax_treatment}
              onChange={(event) => setForm({ ...form, tax_treatment: event.target.value as TaxTreatment })}
            >
              {TAX_TREATMENTS.map((treatment) => (
                <option key={treatment} value={treatment}>
                  {t(`taxTreatment.${treatment}`)}
                </option>
              ))}
            </select>
          </FormField>

          <FormField label={t('demo.scenarioLabel')} htmlFor="demo_scenario" required hint={t('demo.scenarioHint')}>
            <select
              id="demo_scenario"
              className={inputClasses}
              value={form.scenario}
              onChange={(event) => setForm({ ...form, scenario: event.target.value as DemoScenario })}
            >
              {DEMO_SCENARIOS.map((scenario) => (
                <option key={scenario} value={scenario}>
                  {t(`demo.scenario.${scenario}`)}
                </option>
              ))}
            </select>
          </FormField>
        </div>

        {simulateMutation.isError && (
          <p role="alert" className="text-sm text-danger-600">
            {toApiError(simulateMutation.error).message}
          </p>
        )}

        {simulateMutation.isSuccess && (
          <div
            role="status"
            className="rounded-lg border border-success-500/30 bg-success-50 p-3 text-sm text-success-700 dark:bg-success-500/10 dark:text-success-400"
          >
            {t('demo.simulationSuccess')}{' '}
            <Link to="/sales" className="font-semibold underline">
              {t('demo.viewInSales')}
            </Link>
          </div>
        )}

        <button
          type="submit"
          disabled={simulateMutation.isPending}
          className="inline-flex items-center rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {simulateMutation.isPending ? t('demo.simulating') : t('demo.runScenario')}
        </button>
      </form>

      <div className="rounded-2xl border border-danger-500/30 bg-white p-6 shadow-sm dark:border-danger-500/40 dark:bg-stone-900">
        <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">{t('demo.reset.heading')}</h2>
        <p className="mt-2 text-sm text-stone-600 dark:text-stone-400">{t('demo.reset.description')}</p>
        {resetSummary && (
          <p role="status" className="mt-2 text-sm font-medium text-success-700 dark:text-success-400">
            {resetSummary}
          </p>
        )}
        <button
          type="button"
          onClick={() => {
            setResetSummary(null)
            setIsResetDialogOpen(true)
          }}
          className="mt-4 rounded-md border border-danger-500/40 px-4 py-2 text-sm font-semibold text-danger-700 hover:bg-danger-50 dark:text-danger-400 dark:hover:bg-danger-500/10"
        >
          {t('demo.reset.action')}
        </button>
      </div>

      {isResetDialogOpen && (
        <Modal title={t('demo.reset.confirmTitle')} onClose={() => setIsResetDialogOpen(false)}>
          {resetPreviewQuery.isLoading && <LoadingState label={t('common.loading')} />}
          {resetPreviewQuery.isError && (
            <ErrorState message={toApiError(resetPreviewQuery.error).message} onRetry={() => resetPreviewQuery.refetch()} />
          )}
          {resetPreviewQuery.data && (
            <>
              <p className="text-sm text-stone-600 dark:text-stone-400">
                {t('demo.reset.confirmBody', { count: resetPreviewQuery.data.demo_sales_count })}
              </p>
              <p className="mt-2 text-xs text-stone-500 dark:text-stone-400">{t('demo.reset.confirmNote')}</p>
              {resetMutation.isError && (
                <p role="alert" className="mt-2 text-sm text-danger-600">
                  {toApiError(resetMutation.error).message}
                </p>
              )}
              <div className="mt-4 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsResetDialogOpen(false)}
                  className="rounded-md border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:text-stone-200 dark:hover:bg-stone-800"
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="button"
                  disabled={resetMutation.isPending || resetPreviewQuery.data.demo_sales_count === 0}
                  onClick={() => resetMutation.mutate()}
                  className="rounded-md bg-danger-600 px-4 py-2 text-sm font-semibold text-white hover:bg-danger-700 disabled:opacity-60"
                >
                  {resetMutation.isPending ? t('demo.reset.deleting') : t('demo.reset.confirmAction')}
                </button>
              </div>
            </>
          )}
        </Modal>
      )}
    </div>
  )
}
