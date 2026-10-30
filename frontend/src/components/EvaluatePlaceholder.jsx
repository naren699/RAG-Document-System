import { FlaskConical } from 'lucide-react'

function EvaluatePlaceholder() {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="text-center max-w-sm space-y-3">
        <div className="mx-auto w-12 h-12 rounded-[var(--radius-card)] bg-[var(--color-surface-tertiary)] flex items-center justify-center">
          <FlaskConical size={24} className="text-[var(--color-text-tertiary)]" />
        </div>
        <h2 className="text-[20px] font-semibold text-[var(--color-text-primary)]">Evaluate</h2>
        <p className="text-[14px] text-[var(--color-text-secondary)]">
          Run test queries against your documents to measure abstention rate, hallucination score, and retrieval quality.
        </p>
        <p className="text-[12px] text-[var(--color-text-tertiary)]">Coming in Step 7</p>
      </div>
    </div>
  )
}

export default EvaluatePlaceholder
