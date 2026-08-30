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
      <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-500">
        {t('expenses.receiptImageUnavailable')}
      </div>
    )
  }

  return (
    <img
      src={url}
      alt={alt}
      onError={() => setFailed(true)}
      className="max-h-[70vh] w-full rounded-lg border border-slate-200 object-contain"
    />
  )
}
