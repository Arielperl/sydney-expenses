import { useCallback, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp']

export function ReceiptDropzone({
  onFileSelected,
  previewUrl,
}: {
  onFileSelected: (file: File) => void
  previewUrl: string | null
}) {
  const { t } = useTranslation()
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)

  const handleFiles = useCallback(
    (files: FileList | null) => {
      const file = files?.[0]
      if (!file) return
      if (!ACCEPTED_TYPES.includes(file.type)) return
      onFileSelected(file)
    },
    [onFileSelected],
  )

  return (
    <div>
      <div
        onDragOver={(event) => {
          event.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setIsDragging(false)
          handleFiles(event.dataTransfer.files)
        }}
        className={[
          'flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 text-center transition-colors',
          isDragging
            ? 'border-brand-500 bg-brand-50 dark:bg-brand-500/10'
            : 'border-stone-300 bg-white dark:border-stone-700 dark:bg-stone-900',
        ].join(' ')}
      >
        {previewUrl ? (
          <img
            src={previewUrl}
            alt={t('uploadReceipt.previewAlt')}
            className="max-h-64 rounded-lg border border-stone-200 object-contain dark:border-stone-700"
          />
        ) : (
          <p className="text-sm text-stone-500 dark:text-stone-400">{t('uploadReceipt.dropzoneText')}</p>
        )}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="mt-4 inline-flex items-center rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-medium text-stone-700 shadow-sm hover:bg-stone-50 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-200 dark:hover:bg-stone-700"
        >
          {previewUrl ? t('uploadReceipt.chooseDifferentImage') : t('uploadReceipt.chooseImage')}
        </button>
        <p className="mt-2 text-xs text-stone-400 dark:text-stone-500">{t('uploadReceipt.fileHint')}</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_TYPES.join(',')}
          className="sr-only"
          aria-label={t('uploadReceipt.chooseImage')}
          onChange={(event) => handleFiles(event.target.files)}
        />
      </div>
    </div>
  )
}
