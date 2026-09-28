import { X } from 'lucide-react'
import { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'

import { useDialogA11y } from '../hooks/useDialogA11y'

export function DemoVideoDialog({ onClose }: { onClose: () => void }) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const titleId = useId()

  useDialogA11y({ dialogRef, isLoading: false, onClose })

  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeButtonRef.current?.focus()
    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [])

  return createPortal(
    <div className="demo-video-layer" dir="rtl">
      <button
        type="button"
        className="demo-video-backdrop"
        aria-label="סגירת סרטון ההדגמה"
        onClick={onClose}
        tabIndex={-1}
      />
      <div
        ref={dialogRef}
        className="demo-video-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <div className="demo-video-header">
          <div>
            <span>הכירו את Sydney</span>
            <h2 id={titleId}>המערכת ב־30 שניות</h2>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            className="demo-video-close"
            aria-label="סגירה"
            onClick={onClose}
          >
            <X size={20} aria-hidden="true" />
          </button>
        </div>
        <div className="demo-video-frame">
          <video
            controls
            autoPlay
            playsInline
            preload="metadata"
            poster="/media/sydney-demo-poster.jpg"
            aria-label="סרטון הדגמה של מנהל ההכנסות Sydney"
          >
            <source
              src="/media/sydney-demo-30s-vertical.mp4"
              media="(max-width: 640px) and (orientation: portrait)"
              type="video/mp4"
            />
            <source src="/media/sydney-demo-30s.mp4" type="video/mp4" />
            הדפדפן שלכם אינו תומך בהצגת הסרטון.
          </video>
        </div>
      </div>
    </div>,
    document.body,
  )
}
