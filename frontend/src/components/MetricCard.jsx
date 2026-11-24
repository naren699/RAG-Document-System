import { useState } from 'react'

function MetricCard({ title, target, measured, n, ci, formula, icon: Icon, status }) {
  const [showTooltip, setShowTooltip] = useState(false)

  const borderColor = status === 'pass'
    ? 'border-[var(--color-success)]/40'
    : status === 'fail'
      ? 'border-[var(--color-danger)]/40'
      : 'border-[var(--color-border)]'

  return (
    <div
      className={`rounded-[var(--radius-card)] border ${borderColor} bg-[var(--color-surface)] p-4 relative`}
      onMouseEnter={() => formula && setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <div className="flex items-center gap-2 mb-2">
        {Icon && <Icon size={16} className="text-[var(--color-text-tertiary)]" />}
        <span className="text-[13px] font-medium text-[var(--color-text-primary)]">{title}</span>
      </div>
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-[12px] text-[var(--color-text-tertiary)]">Target</span>
          <span className="text-[14px] font-medium text-[var(--color-text-primary)]">{target || '—'}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[12px] text-[var(--color-text-tertiary)]">Measured</span>
          <span className={`text-[14px] font-medium ${
            measured == null
              ? 'text-[var(--color-text-tertiary)] italic'
              : status === 'pass'
                ? 'text-[var(--color-success)]'
                : status === 'fail'
                  ? 'text-[var(--color-danger)]'
                  : 'text-[var(--color-text-primary)]'
          }`}>
            {measured != null ? measured : 'Not measured yet'}
          </span>
        </div>
        {n != null && (
          <div className="flex items-center justify-between">
            <span className="text-[12px] text-[var(--color-text-tertiary)]">n</span>
            <span className="text-[12px] text-[var(--color-text-secondary)] tabular-nums">{n}</span>
          </div>
        )}
        {ci && (
          <div className="flex items-center justify-between">
            <span className="text-[12px] text-[var(--color-text-tertiary)]">95% CI</span>
            <span className="text-[11px] text-[var(--color-text-tertiary)] tabular-nums">[{ci[0]}, {ci[1]}]</span>
          </div>
        )}
      </div>

      {showTooltip && formula && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-[var(--color-surface-tertiary)] border border-[var(--color-border)] rounded-[var(--radius-btn)] text-[11px] text-[var(--color-text-secondary)] whitespace-nowrap z-10 shadow-sm">
          {formula}
        </div>
      )}
    </div>
  )
}

export default MetricCard
