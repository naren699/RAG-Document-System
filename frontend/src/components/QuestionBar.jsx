import { useState, useRef, useEffect } from 'react'
import { Send, Loader2, Clock, Square } from 'lucide-react'

const STAGES = [
  { after: 0, text: 'Searching documents...' },
  { after: 1.5, text: 'Reading chunks...' },
  { after: 4, text: 'Writing answer...' },
]

function QuestionBar({ query, onQueryChange, onSearch, onStop, isSearching, disabled, searchHistory, onSelectHistory }) {
  const [showHistory, setShowHistory] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const wrapperRef = useRef(null)
  const inputRef = useRef(null)

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !disabled && !isSearching && query.trim()) {
      e.preventDefault()
      onSearch()
    }
  }

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) setShowHistory(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    if (!isSearching) { setElapsed(0); return }
    const start = Date.now()
    const interval = setInterval(() => setElapsed((Date.now() - start) / 1000), 100)
    return () => clearInterval(interval)
  }, [isSearching])

  useEffect(() => {
    const handleSlash = (e) => {
      if (e.key === '/' && !e.ctrlKey && !e.metaKey && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    document.addEventListener('keydown', handleSlash)
    return () => document.removeEventListener('keydown', handleSlash)
  }, [])

  const stageText = STAGES.filter(s => elapsed >= s.after).pop()?.text || ''
  const history = searchHistory || []

  return (
    <div className="border-t border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 transition-theme">
      <div className="max-w-3xl mx-auto" ref={wrapperRef}>
        <div className="relative flex items-end gap-2">
          <div className="relative flex-1">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => onQueryChange(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => history.length > 0 && !query.trim() && setShowHistory(true)}
              placeholder={disabled ? 'Upload a document first...' : 'Ask a question... (press / to focus)'}
              disabled={disabled || isSearching}
              className="w-full border border-[var(--color-border)] bg-[var(--color-surface)] text-[14px] text-[var(--color-text-primary)] placeholder-[var(--color-text-tertiary)] rounded-[var(--radius-input)] pl-4 pr-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed transition-theme"
              aria-label="Question input"
            />

            {showHistory && history.length > 0 && (
              <div className="absolute bottom-full left-0 right-0 mb-1 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-card)] shadow-[var(--shadow-popover)] z-10 max-h-48 overflow-y-auto">
                <div className="px-3 py-1.5 text-[12px] text-[var(--color-text-tertiary)] font-medium uppercase tracking-wide">Recent</div>
                {history.map((item, i) => (
                  <button
                    key={i}
                    onClick={() => { onSelectHistory(item); setShowHistory(false) }}
                    className="w-full text-left px-3 py-2 text-[14px] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-tertiary)] transition-theme flex items-center gap-2"
                  >
                    <Clock size={14} className="text-[var(--color-text-tertiary)] shrink-0" />
                    <span className="truncate">{item}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {isSearching ? (
            <button
              onClick={onStop}
              className="flex items-center justify-center h-[42px] w-[42px] rounded-[var(--radius-btn)] bg-[var(--color-danger)] text-[var(--color-text-inverse)] hover:bg-red-700 transition-theme shrink-0"
              aria-label="Stop generation"
              title="Stop"
            >
              <Square size={16} fill="currentColor" />
            </button>
          ) : (
            <button
              onClick={onSearch}
              disabled={disabled || !query.trim()}
              className="flex items-center justify-center h-[42px] w-[42px] rounded-[var(--radius-btn)] bg-[var(--color-accent)] text-[var(--color-text-inverse)] hover:bg-[var(--color-accent-hover)] disabled:opacity-40 disabled:cursor-not-allowed transition-theme shrink-0"
              aria-label="Send question"
            >
              <Send size={18} />
            </button>
          )}
        </div>

        {isSearching && elapsed > 0 && (
          <div className="flex items-center justify-center gap-2 mt-1.5">
            <Loader2 size={12} className="animate-spin text-[var(--color-text-tertiary)]" />
            <span className="text-[12px] text-[var(--color-text-tertiary)]">
              {stageText} {elapsed.toFixed(1)}s
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

export default QuestionBar
