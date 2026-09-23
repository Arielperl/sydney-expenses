import { useState } from 'react'
import { useTranslation } from 'react-i18next'

/**
 * Renders a receipt image from a (possibly time-limited, e.g. Supabase signed)
 * URL. If the URL has expired or is otherwise unreachable, the browser's <img>
 * onerror event fires and we swap to a plain-text fallback instead of a broken
 * image icon — the underlying receipt data is never lost, only the preview.
 */
export function ReceiptImage({ url, alt }: { url: string; alt: string }) {
  const { t } = useTranslation()
  const [failed, setFailed] = useState(false)

  if (failed) {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-zinc-300 bg-zinc-50 text-sm text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400">
        {t('sales.documentImageUnavailable')}
      </div>
    )
  }

  return (
    <img
      src={url}
      alt={alt}
      onError={() => setFailed(true)}
      className="max-h-[70vh] w-full rounded-lg border border-zinc-200 object-contain dark:border-zinc-700"
    />
  )
}
