import { useQuery } from '@tanstack/react-query'
import { FileSpreadsheet, PlugZap } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { CardcomConnectionPanel } from '../components/CardcomConnectionPanel'
import { CsvImportWizard } from '../components/CsvImportWizard'
import { GrowConnectionPanel } from '../components/GrowConnectionPanel'
import { getBusinessPaymentProviders } from '../services/businessService'
import { EmptyState, ErrorState, LoadingState } from '../components/StatusStates'
import { PageHeader } from '../components/ui'
import { cx } from '../components/ui-classes'

export function ImportsPage() {
  const { t } = useTranslation()
  const [section, setSection] = useState<'connections' | 'csv'>('connections')
  const [csvVisited, setCsvVisited] = useState(false)
  function selectSection(next: 'connections' | 'csv') {
    setSection(next)
    if (next === 'csv') setCsvVisited(true)
  }
  const { data: providers, isPending: isLoading, isError } = useQuery({
    queryKey: ['business-payment-providers'],
    queryFn: getBusinessPaymentProviders,
  })

  return (
    <div className="max-w-4xl space-y-6">
      <PageHeader title={t('imports.title')} description={t('imports.subtitle')} />

      <div role="tablist" aria-label={t('imports.sectionsLabel')} className="flex gap-6 border-b border-zinc-200 dark:border-zinc-800">
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
            className={cx(
              '-mb-px inline-flex items-center gap-2 border-b-2 px-0.5 pt-1 pb-3 text-sm font-medium transition-colors',
              section === item
                ? 'border-brand-600 text-zinc-900 dark:border-brand-400 dark:text-zinc-50'
                : 'border-transparent text-zinc-500 hover:border-zinc-300 hover:text-zinc-800 dark:text-zinc-400 dark:hover:border-zinc-600 dark:hover:text-zinc-100',
            )}
          >
            {item === 'connections' ? <PlugZap className="h-4 w-4" aria-hidden="true" /> : <FileSpreadsheet className="h-4 w-4" aria-hidden="true" />}
            {t(`imports.sections.${item}`)}
          </button>
        ))}
      </div>

      <div id="imports-panel-connections" role="tabpanel" aria-labelledby="imports-tab-connections" hidden={section !== 'connections'} className="space-y-5">
        {isLoading && <LoadingState label={t('imports.providersLoading')} />}
        {isError && <ErrorState message={t('imports.providersError')} />}
        {providers?.includes('grow') && <GrowConnectionPanel />}
        {providers?.includes('cardcom') && <CardcomConnectionPanel />}
        {providers && providers.length === 0 && (
          <EmptyState title={t('imports.noProvidersTitle')} description={t('imports.noProvidersDescription')} icon={<PlugZap className="h-5 w-5" />} />
        )}
        {providers && providers.length > 0 && <p className="text-sm text-zinc-500 dark:text-zinc-400">{t('imports.addProviderSupport')}</p>}
      </div>
      <div id="imports-panel-csv" role="tabpanel" aria-labelledby="imports-tab-csv" hidden={section !== 'csv'}>
        {csvVisited && <CsvImportWizard />}
      </div>
    </div>
  )
}
