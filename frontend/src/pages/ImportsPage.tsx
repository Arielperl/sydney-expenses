import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { CardcomConnectionPanel } from '../components/CardcomConnectionPanel'
import { CsvImportWizard } from '../components/CsvImportWizard'
import { GrowConnectionPanel } from '../components/GrowConnectionPanel'
import { getBusinessPaymentProviders } from '../services/businessService'

export function ImportsPage() {
  const { t } = useTranslation()
  const [section, setSection] = useState<'connections' | 'csv'>('connections')
  const [csvVisited, setCsvVisited] = useState(false)
  function selectSection(next: 'connections' | 'csv') {
    setSection(next)
    if (next === 'csv') setCsvVisited(true)
  }
  const { data: providers, isLoading, isError } = useQuery({
    queryKey: ['business-payment-providers'],
    queryFn: getBusinessPaymentProviders,
  })

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">{t('imports.title')}</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{t('imports.subtitle')}</p>
      </div>

      <div role="tablist" aria-label={t('imports.sectionsLabel')} className="flex gap-1 rounded-xl border border-zinc-200 bg-zinc-50 p-1 dark:border-zinc-800 dark:bg-zinc-900">
        {(['connections', 'csv'] as const).map((item) => (
          <button
            key={item}
            type="button"
            role="tab"
            id={`imports-tab-${item}`}
            aria-controls={`imports-panel-${item}`}
            aria-selected={section === item}
            tabIndex={section === item ? 0 : -1}
            onClick={() => selectSection(item)}
            onKeyDown={(event) => {
              const forward = document.documentElement.dir === 'rtl' ? 'ArrowLeft' : 'ArrowRight'
              const backward = document.documentElement.dir === 'rtl' ? 'ArrowRight' : 'ArrowLeft'
              let next: 'connections' | 'csv' | null = null
              if (event.key === forward) next = item === 'connections' ? 'csv' : 'connections'
              if (event.key === backward) next = item === 'csv' ? 'connections' : 'csv'
              if (event.key === 'Home') next = 'connections'
              if (event.key === 'End') next = 'csv'
              if (next) {
                event.preventDefault()
                selectSection(next)
                document.getElementById(`imports-tab-${next}`)?.focus()
              }
            }}
            className={`flex-1 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${section === item ? 'bg-white text-brand-700 shadow-sm dark:bg-zinc-800 dark:text-brand-400' : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100'}`}
          >
            {t(`imports.sections.${item}`)}
          </button>
        ))}
      </div>

      <div id="imports-panel-connections" role="tabpanel" aria-labelledby="imports-tab-connections" hidden={section !== 'connections'} className="space-y-5">
        {isLoading && <div className="rounded-xl border border-zinc-200 bg-white p-5 text-sm text-zinc-500">{t('imports.providersLoading')}</div>}
        {isError && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">{t('imports.providersError')}</div>}
        {providers?.includes('grow') && <GrowConnectionPanel />}
        {providers?.includes('cardcom') && <CardcomConnectionPanel />}
        {providers && providers.length === 0 && (
          <div className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-700 dark:bg-zinc-900">
            <h2 className="font-semibold text-zinc-900 dark:text-zinc-100">{t('imports.noProvidersTitle')}</h2>
            <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{t('imports.noProvidersDescription')}</p>
          </div>
        )}
        {providers && providers.length > 0 && <p className="text-sm text-zinc-500 dark:text-zinc-400">{t('imports.addProviderSupport')}</p>}
      </div>
      <div id="imports-panel-csv" role="tabpanel" aria-labelledby="imports-tab-csv" hidden={section !== 'csv'}>
        {csvVisited && <CsvImportWizard />}
      </div>
    </div>
  )
}
