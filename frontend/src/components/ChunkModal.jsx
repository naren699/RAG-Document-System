import CopyButton from './CopyButton'

function HighlightedText({ text, query }) {
  if (!query?.trim()) return <span>{text}</span>
  const words = query.trim().split(/\s+/).filter(w => w.length > 2)
  if (!words.length) return <span>{text}</span>
  const escaped = words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const pattern = new RegExp(`(${escaped.join('|')})`, 'gi')
  const parts = text.split(pattern)
  return (
    <span>
      {parts.map((part, i) =>
        pattern.test(part)
          ? <mark key={i} className="bg-yellow-200 rounded px-0.5">{part}</mark>
          : <span key={i}>{part}</span>
      )}
    </span>
  )
}

function ChunkModal({ chunk, query, onClose }) {
  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <span className="inline-block bg-blue-100 text-blue-800 text-sm font-medium px-2.5 py-0.5 rounded">
              Page {chunk.page_num}
            </span>
            {chunk.doc_id && (
              <span className="text-sm text-gray-400">{chunk.doc_id}</span>
            )}
            <span className="text-sm text-gray-400">
              Score: {(chunk.score * 100).toFixed(1)}%
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="bg-gray-50 rounded-lg p-4">
          <p className="text-gray-800 leading-relaxed whitespace-pre-wrap">
            <HighlightedText text={chunk.text} query={query} />
          </p>
        </div>

        <div className="flex items-center justify-between mt-3">
          {chunk.token_count > 0 && (
            <p className="text-xs text-gray-400">{chunk.token_count} tokens</p>
          )}
          <CopyButton text={chunk.text} label="Copy chunk" />
        </div>
      </div>
    </div>
  )
}

export default ChunkModal
