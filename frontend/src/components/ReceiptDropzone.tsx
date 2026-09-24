import { FileUp } from 'lucide-react'
import { useCallback, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { buttonClasses } from './ui-classes'

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
          'flex flex-col items-center justify-center rounded-xl border border-dashed px-6 py-10 text-center transition-colors duration-150',
          isDragging
            ? 'border-brand-500 bg-brand-50 ring-3 ring-brand-500/15 dark:bg-brand-500/10'
            : 'border-zinc-300 bg-zinc-50/60 dark:border-zinc-700 dark:bg-zinc-950/30',
        ].join(' ')}
      >
        {previewUrl ? (
          <img
            src={previewUrl}
            alt={t('uploadReceipt.previewAlt')}
            className="max-h-64 rounded-lg border border-zinc-200 object-contain dark:border-zinc-700"
          />
        ) : (
          <>
            <span className="mb-3 grid h-11 w-11 place-items-center rounded-full bg-white text-brand-700 shadow-card ring-1 ring-zinc-200 dark:bg-zinc-900 dark:text-brand-300 dark:ring-zinc-700" aria-hidden="true">
              <FileUp className="h-5 w-5" />
            </span>
            <p className="text-sm text-zinc-600 dark:text-zinc-300">{t('uploadReceipt.dropzoneText')}</p>
          </>
        )}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className={buttonClasses('secondary', 'md', 'mt-4')}
        >
          {previewUrl ? t('uploadReceipt.chooseDifferentImage') : t('uploadReceipt.chooseImage')}
        </button>
        <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">{t('uploadReceipt.fileHint')}</p>
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
