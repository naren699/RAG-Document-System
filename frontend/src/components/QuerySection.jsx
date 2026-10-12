function QuerySection({ query, onQueryChange, onSearch, isSearching, disabled }) {
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !disabled && !isSearching) onSearch()
  }

  return (
    <section className="bg-white rounded-lg border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Ask a Question</h2>
      <div className="flex gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={disabled ? 'Upload a document first...' : 'What would you like to know?'}
          disabled={disabled}
          className="flex-1 border border-gray-300 rounded-lg px-4 py-2.5 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
        />
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
    </section>
  )
}

export default QuerySection
