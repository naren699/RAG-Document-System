function ConfusionMatrix({ confusion }) {
  if (!confusion) return null
  const { tp, fp, fn, tn } = confusion

  const cell = (value, label, isCorrect) => (
    <div className={`p-3 rounded-[var(--radius-btn)] text-center ${
      isCorrect
        ? 'bg-[var(--color-success-subtle)]'
        : 'bg-[var(--color-danger-subtle)]'
    }`}>
      <p className="text-[20px] font-bold text-[var(--color-text-primary)] tabular-nums">{value}</p>
      <p className="text-[11px] text-[var(--color-text-tertiary)] mt-0.5">{label}</p>
    </div>
  )

  return (
    <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <p className="text-[13px] font-medium text-[var(--color-text-primary)] mb-3">Refusal Confusion Matrix</p>
      <div className="grid grid-cols-[auto_1fr_1fr] gap-1.5 text-[12px]">
        {/* Header row */}
        <div />
        <div className="text-center text-[var(--color-text-tertiary)] font-medium pb-1">System Answers</div>
        <div className="text-center text-[var(--color-text-tertiary)] font-medium pb-1">System Refuses</div>

        {/* Answerable row */}
        <div className="flex items-center pr-2 text-[var(--color-text-tertiary)] font-medium">Answerable</div>
        {cell(tn, 'Correct answer', true)}
        {cell(fp, 'Wrong refusal', false)}

        {/* Unanswerable row */}
        <div className="flex items-center pr-2 text-[var(--color-text-tertiary)] font-medium">Unanswerable</div>
        {cell(fn, 'Should have refused', false)}
        {cell(tp, 'Correct refusal', true)}
      </div>
    </div>
  )
}

export default ConfusionMatrix
