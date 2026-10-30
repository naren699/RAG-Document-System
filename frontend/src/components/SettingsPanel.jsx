import { useState } from 'react'

function SettingsPanel({ settings, onChange }) {
  const [expanded, setExpanded] = useState(false)

  const update = (key, value) => onChange({ ...settings, [key]: value })

  return (
    <section className="bg-white rounded-lg border border-gray-200">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-6 py-3 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
      >
        <span className="font-medium">Search Settings</span>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400">
            k={settings.topK} · {settings.method} · threshold={settings.scoreThreshold}
          </span>
          <svg
            className={`h-4 w-4 transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {expanded && (
        <div className="px-6 pb-5 pt-2 border-t border-gray-100 space-y-4">
          {/* Top-K */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Top-K Results: {settings.topK}
            </label>
            <input
              type="range"
              min="1" max="10" step="1"
              value={settings.topK}
              onChange={(e) => update('topK', parseInt(e.target.value))}
              className="w-full accent-blue-600"
            />
            <div className="flex justify-between text-xs text-gray-400">
              <span>1</span>
              <span>10</span>
            </div>
          </div>

          {/* Retrieval Mode */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Retrieval Mode
            </label>
            <select
              value={settings.method}
              onChange={(e) => update('method', e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="hybrid">Hybrid (Vector + BM25)</option>
              <option value="dense">Vector Only</option>
              <option value="bm25">Keyword Only (BM25)</option>
            </select>
          </div>

          {/* Score Threshold — cross-encoder raw logit */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Rerank Score Threshold: {settings.scoreThreshold.toFixed(1)}
            </label>
            <input
              type="range"
              min="-5" max="10" step="0.5"
              value={settings.scoreThreshold}
              onChange={(e) => update('scoreThreshold', parseFloat(e.target.value))}
              className="w-full accent-blue-600"
            />
            <div className="flex justify-between text-xs text-gray-400">
              <span>-5 (keep all)</span>
              <span>10 (strict)</span>
            </div>
          </div>

          {/* PII Masking */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="mask-pii"
              checked={settings.maskPii || false}
              onChange={(e) => update('maskPii', e.target.checked)}
              className="accent-blue-600"
            />
            <label htmlFor="mask-pii" className="text-sm text-gray-700">
              Mask personal data (emails, phone numbers) before sending to LLM
            </label>
          </div>

          <p className="text-xs text-gray-400">
            Threshold applies to the cross-encoder rerank score (raw logit). Higher = stricter filtering. Default is -2.
          </p>
        </div>
      )}
    </section>
  )
}

export default SettingsPanel
