import { useTranslation } from 'react-i18next'

import { CsvImportWizard } from '../components/CsvImportWizard'
import { ConnectionsPanel } from '../components/ConnectionsPanel'

export function ImportsPage() {
  const { t } = useTranslation()

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">{t('imports.title')}</h1>
        <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('imports.subtitle')}</p>
      </div>

      <CsvImportWizard />

      <ConnectionsPanel />
    </div>
  )
}
