import { useEffect } from 'react'
import { CheckCircle2, XCircle, AlertTriangle, X } from 'lucide-react'

const ICONS = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
}

const STYLES = {
  success: 'bg-[var(--color-success-subtle)] text-[var(--color-success)] border-[var(--color-success)]/20',
  error: 'bg-[var(--color-danger-subtle)] text-[var(--color-danger)] border-[var(--color-danger)]/20',
  warning: 'bg-[var(--color-warning-subtle)] text-[var(--color-warning)] border-[var(--color-warning)]/20',
}

function Toast({ message, type = 'success', onClose, duration = 4000 }) {
  useEffect(() => {
    if (!message) return
    const timer = setTimeout(onClose, duration)
    return () => clearTimeout(timer)
  }, [message, duration, onClose])

  if (!message) return null

  const Icon = ICONS[type] || ICONS.success

  return (
    <div className="fixed bottom-20 left-1/2 -translate-x-1/2 z-50 animate-slide-up">
      <div className={`flex items-center gap-2 px-4 py-2.5 rounded-[var(--radius-btn)] border shadow-[var(--shadow-popover)] text-[14px] ${STYLES[type]}`}>
        <Icon size={16} className="shrink-0" />
        <span>{message}</span>
        <button onClick={onClose} className="p-0.5 hover:opacity-70 shrink-0" aria-label="Close">
          <X size={14} />
        </button>
      </div>
    </div>
  )
}

export default Toast
