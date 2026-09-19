import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { CardcomConnectionPanel } from '../components/CardcomConnectionPanel'
import { CsvImportWizard } from '../components/CsvImportWizard'
import { GrowConnectionPanel } from '../components/GrowConnectionPanel'
import { getBusinessPaymentProviders } from '../services/businessService'

export function ImportsPage() {
  const { t } = useTranslation()
  const { data: providers, isLoading, isError } = useQuery({
    queryKey: ['business-payment-providers'],
    queryFn: getBusinessPaymentProviders,
  })

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">{t('imports.title')}</h1>
        <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('imports.subtitle')}</p>
      </div>

      {isLoading && <div className="rounded-xl border border-stone-200 bg-white p-5 text-sm text-stone-500">{t('imports.providersLoading')}</div>}
      {isError && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">{t('imports.providersError')}</div>}
      {providers?.includes('grow') && <GrowConnectionPanel />}
      {providers?.includes('cardcom') && <CardcomConnectionPanel />}
      {providers && providers.length === 0 && (
        <div className="rounded-xl border border-stone-200 bg-white p-5 dark:border-stone-700 dark:bg-stone-900">
          <h2 className="font-semibold text-stone-900 dark:text-stone-100">{t('imports.noProvidersTitle')}</h2>
          <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('imports.noProvidersDescription')}</p>
        </div>
      )}
      {providers && providers.length > 0 && (
        <p className="text-sm text-stone-500 dark:text-stone-400">{t('imports.addProviderSupport')}</p>
      )}
      <CsvImportWizard />
    </div>
  )
}
