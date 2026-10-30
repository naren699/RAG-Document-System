import { useState } from 'react'
import { ChevronDown, Settings, RotateCcw } from 'lucide-react'

const DEFAULTS = { topK: 5, method: 'hybrid', scoreThreshold: -2.0, maskPii: false }

function SettingsPanel({ settings, onChange }) {
  const [expanded, setExpanded] = useState(false)

  const update = (key, value) => onChange({ ...settings, [key]: value })
  const reset = () => onChange({ ...DEFAULTS })

  const methodLabel = { hybrid: 'Hybrid', dense: 'Vector', bm25: 'BM25' }[settings.method] || settings.method

  return (
    <section className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] transition-theme">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 text-[14px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-tertiary)] transition-theme rounded-[var(--radius-card)]"
      >
        <div className="flex items-center gap-2">
          <Settings size={15} className="text-[var(--color-text-tertiary)]" />
          <span className="font-medium text-[var(--color-text-primary)]">Settings</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[12px] text-[var(--color-text-tertiary)] bg-[var(--color-surface-tertiary)] px-2 py-0.5 rounded-full">
            k={settings.topK} · {methodLabel} · {settings.scoreThreshold.toFixed(1)}
          </span>
          <ChevronDown
            size={16}
            className={`text-[var(--color-text-tertiary)] transition-transform duration-150 ${expanded ? 'rotate-180' : ''}`}
          />
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-2 border-t border-[var(--color-border)] space-y-4">
          <div>
            <label className="block text-[14px] font-medium text-[var(--color-text-primary)] mb-1">
              Top-K Results: <span className="text-[var(--color-accent)]">{settings.topK}</span>
            </label>
            <input
              type="range" min="1" max="10" step="1"
              value={settings.topK}
              onChange={(e) => update('topK', parseInt(e.target.value))}
              className="w-full accent-[var(--color-accent)]"
            />
            <div className="flex justify-between text-[12px] text-[var(--color-text-tertiary)]">
              <span>1</span><span>10</span>
            </div>
          </div>

          <div>
            <label className="block text-[14px] font-medium text-[var(--color-text-primary)] mb-1">
              Retrieval Mode
            </label>
            <select
              value={settings.method}
              onChange={(e) => update('method', e.target.value)}
              className="w-full border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-primary)] rounded-[var(--radius-input)] px-3 py-2 text-[14px] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]"
            >
              <option value="hybrid">Hybrid (Vector + BM25)</option>
              <option value="dense">Vector Only</option>
              <option value="bm25">Keyword Only (BM25)</option>
            </select>
          </div>

          <div>
            <label className="block text-[14px] font-medium text-[var(--color-text-primary)] mb-1">
              Rerank Threshold: <span className="text-[var(--color-accent)]">{settings.scoreThreshold.toFixed(1)}</span>
            </label>
            <input
              type="range" min="-5" max="10" step="0.5"
              value={settings.scoreThreshold}
              onChange={(e) => update('scoreThreshold', parseFloat(e.target.value))}
              className="w-full accent-[var(--color-accent)]"
            />
            <div className="flex justify-between text-[12px] text-[var(--color-text-tertiary)]">
              <span>-5 (keep all)</span><span>10 (strict)</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox" id="mask-pii"
              checked={settings.maskPii || false}
              onChange={(e) => update('maskPii', e.target.checked)}
              className="accent-[var(--color-accent)]"
            />
            <label htmlFor="mask-pii" className="text-[14px] text-[var(--color-text-secondary)]">
              Mask personal data before sending to LLM
            </label>
          </div>

          <button
            onClick={reset}
            className="flex items-center gap-1.5 text-[12px] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)] transition-theme"
          >
            <RotateCcw size={12} />
            Reset to defaults
          </button>
        </div>
      )}
    </section>
  )
}

export default SettingsPanel
