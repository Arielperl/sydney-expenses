import { useEffect, useRef, type RefObject } from 'react'

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

// Shared accessible-dialog behavior for any custom modal in this app:
// restores focus to whatever triggered the dialog once it unmounts, traps
// Tab navigation inside the dialog, and closes on Escape — all suspended
// while `isLoading` so an in-flight request can't be dismissed out from
// under itself. Each dialog still owns its own initial-focus target (which
// element to focus, whether to select its text, etc.) since that varies.
export function useDialogA11y({
  dialogRef,
  isLoading,
  onClose,
}: {
  dialogRef: RefObject<HTMLElement | null>
  isLoading: boolean
  onClose: () => void
}) {
  const previouslyFocused = useRef<HTMLElement | null>(null)

  useEffect(() => {
    previouslyFocused.current = document.activeElement as HTMLElement | null
    return () => {
      previouslyFocused.current?.focus?.()
    }
    // Runs once on mount/unmount only — capturing and restoring focus should
    // not re-trigger when isLoading or onClose change mid-dialog.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        if (isLoading) return
        event.preventDefault()
        onClose()
        return
      }
      if (event.key !== 'Tab' || !dialogRef.current) return
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isLoading, onClose, dialogRef])
}
