import { useState, useRef, useEffect } from 'react'

function QuerySection({ query, onQueryChange, onSearch, isSearching, disabled, searchHistory, onSelectHistory }) {
  const [showHistory, setShowHistory] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const wrapperRef = useRef(null)

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !disabled && !isSearching) onSearch()
  }

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setShowHistory(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    if (!isSearching) { setElapsed(0); return }
    const start = Date.now()
    const interval = setInterval(() => setElapsed(((Date.now() - start) / 1000).toFixed(1)), 100)
    return () => clearInterval(interval)
  }, [isSearching])

  const history = searchHistory || []

  return (
    <section className="bg-white rounded-lg border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Ask a Question</h2>
      <div className="flex gap-3" ref={wrapperRef}>
        <div className="relative flex-1">
          <input
            type="text"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => history.length > 0 && setShowHistory(true)}
            placeholder={disabled ? 'Upload a document first...' : 'What would you like to know?'}
            disabled={disabled}
            className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
          />
          {showHistory && history.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-10 max-h-48 overflow-y-auto">
              <div className="px-3 py-1.5 text-xs text-gray-400 font-medium uppercase tracking-wide">Recent searches</div>
              {history.map((item, i) => (
                <button
                  key={i}
                  onClick={() => {
                    onSelectHistory(item)
                    setShowHistory(false)
                  }}
                  className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-blue-50 hover:text-blue-700 transition-colors flex items-center gap-2"
                >
                  <svg className="h-3.5 w-3.5 text-gray-300 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="truncate">{item}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <button
          onClick={onSearch}
          disabled={disabled || isSearching || !query.trim()}
          className="bg-blue-600 text-white px-6 py-2.5 rounded-lg hover:bg-blue-700 disabled:bg-blue-300 transition-colors font-medium whitespace-nowrap flex items-center gap-2"
        >
          {isSearching && (
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          )}
          {isSearching ? 'Searching...' : 'Search'}
        </button>
      </div>
      {isSearching && elapsed > 0 && (
        <p className="text-sm text-gray-400 mt-2 text-center">Searching... {elapsed}s</p>
      )}
    </section>
  )
}

export default QuerySection
