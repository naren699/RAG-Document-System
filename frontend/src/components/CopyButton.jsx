import { useState } from 'react'
import { Copy, Check } from 'lucide-react'

function CopyButton({ text, label }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      onClick={(e) => { e.stopPropagation(); handleCopy() }}
      className="min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 flex items-center justify-center gap-1 px-2 py-1.5 text-[12px] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)] rounded-[var(--radius-btn)] hover:bg-[var(--color-surface-tertiary)] transition-theme"
      aria-label={copied ? 'Copied to clipboard' : `Copy ${label || 'text'}`}
    >
      {copied ? (
        <>
          <Check size={14} className="text-[var(--color-success)]" />
          <span className="hidden sm:inline">Copied</span>
        </>
      ) : (
        <>
          <Copy size={14} />
          {label && <span className="hidden sm:inline">{label}</span>}
        </>
      )}
    </button>
  )
}

export default CopyButton
