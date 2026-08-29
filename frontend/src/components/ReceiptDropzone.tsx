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
          'flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition-colors',
          isDragging ? 'border-brand-500 bg-brand-50' : 'border-slate-300 bg-white',
        ].join(' ')}
      >
        {previewUrl ? (
          <img
            src={previewUrl}
            alt={t('uploadReceipt.previewAlt')}
            className="max-h-64 rounded-lg border border-slate-200 object-contain"
          />
        ) : (
          <p className="text-sm text-slate-500">{t('uploadReceipt.dropzoneText')}</p>
        )}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="mt-4 inline-flex items-center rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
        >
          {previewUrl ? t('uploadReceipt.chooseDifferentImage') : t('uploadReceipt.chooseImage')}
        </button>
        <p className="mt-2 text-xs text-slate-400">{t('uploadReceipt.fileHint')}</p>
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
