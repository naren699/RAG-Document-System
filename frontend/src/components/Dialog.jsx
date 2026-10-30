import { useEffect, useRef } from 'react'
import { X, AlertTriangle } from 'lucide-react'

function Dialog({ open, onClose, title, description, danger, confirmLabel, onConfirm, children }) {
  const overlayRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const handleKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <div className="absolute inset-0 bg-black/40" />
      <div
        className="relative bg-[var(--color-surface)] rounded-[var(--radius-card)] shadow-[var(--shadow-popover)] w-full max-w-sm p-6 space-y-4"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="flex items-start gap-3">
          {danger && (
            <div className="w-8 h-8 rounded-full bg-[var(--color-danger-subtle)] flex items-center justify-center shrink-0">
              <AlertTriangle size={16} className="text-[var(--color-danger)]" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <h3 className="text-[16px] font-semibold text-[var(--color-text-primary)]">{title}</h3>
            {description && <p className="text-[14px] text-[var(--color-text-secondary)] mt-1">{description}</p>}
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-[var(--radius-btn)] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-tertiary)]"
            aria-label="Close dialog"
          >
            <X size={16} />
          </button>
        </div>

        {children}

        <div className="flex items-center justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-[14px] font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] rounded-[var(--radius-btn)] hover:bg-[var(--color-surface-tertiary)] transition-theme"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 text-[14px] font-medium text-[var(--color-text-inverse)] rounded-[var(--radius-btn)] transition-theme ${
              danger
                ? 'bg-[var(--color-danger)] hover:bg-red-700'
                : 'bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)]'
            }`}
          >
            {confirmLabel || 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default Dialog
