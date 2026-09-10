import { useTranslation } from 'react-i18next'

import { CsvImportWizard } from '../components/CsvImportWizard'

export function ImportsPage() {
  const { t } = useTranslation()

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">{t('imports.title')}</h1>
        <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('imports.subtitle')}</p>
      </div>

      <CsvImportWizard />

      <div className="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm dark:border-stone-800 dark:bg-stone-900">
        <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">{t('imports.webhook.heading')}</h2>
        <p className="mt-2 text-sm text-stone-600 dark:text-stone-400">
          <span className="font-medium">{t('imports.webhook.statusLabel')}:</span> {t('imports.webhook.statusValue')}
        </p>
        <p className="mt-2 text-sm text-stone-600 dark:text-stone-400">{t('imports.webhook.description')}</p>
        <p className="mt-4 text-sm font-medium text-stone-700 dark:text-stone-300">{t('imports.webhook.instructions')}</p>
        <pre className="mt-2 overflow-x-auto rounded-lg bg-stone-100 p-3 text-xs text-stone-800 dark:bg-stone-800 dark:text-stone-200">
          <code dir="ltr">
            {`cd backend && source .venv/bin/activate
export WEBHOOK_SIGNING_SECRET=demo-secret-change-me
python -m scripts.demo_webhook_request`}
          </code>
        </pre>
      </div>
    </div>
  )
}
