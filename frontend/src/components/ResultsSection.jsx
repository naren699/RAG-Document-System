import { useState } from 'react'
import ChunkModal from './ChunkModal'

function scoreColor(score) {
  if (score >= 0.7) return 'bg-green-500'
  if (score >= 0.4) return 'bg-yellow-500'
  return 'bg-red-400'
}

function scoreLabel(score) {
  if (score >= 0.7) return 'text-green-700 bg-green-50'
  if (score >= 0.4) return 'text-yellow-700 bg-yellow-50'
  return 'text-red-700 bg-red-50'
}

function CopyButton({ text, label }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      onClick={handleCopy}
      className="text-xs text-gray-400 hover:text-gray-600 transition-colors flex items-center gap-1"
    >
      {copied ? (
        <>
          <svg className="h-3.5 w-3.5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          Copied
        </>
      ) : (
        <>
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          {label}
        </>
      )}
    </button>
  )
}

function ResultsSection({ result }) {
  const [selectedChunk, setSelectedChunk] = useState(null)

  const sources = result.sources || []
  const maxScore = sources.length > 0 ? Math.max(...sources.map(s => s.score || 0)) : 0
  const lowConfidence = sources.length > 0 && maxScore < 0.4

  const sourcesText = sources.map((s, i) =>
    `[${i + 1}] Page ${s.page_num} (score: ${s.score})\n${s.text}`
  ).join('\n\n')

  return (
    <section className="space-y-6">
      {/* Answer */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Answer</h2>
          <div className="flex items-center gap-3">
            {result.provider && (
              <span className="text-xs text-gray-400">
                {result.provider}/{result.model}
              </span>
            )}
            <CopyButton text={result.answer} label="Copy" />
          </div>
        </div>

        <div className="bg-gray-50 rounded-lg p-4">
          <p className="text-gray-800 leading-relaxed whitespace-pre-wrap">{result.answer}</p>
        </div>

        {result.timings && (
          <div className="flex gap-4 mt-3 text-xs text-gray-400">
            <span>Retrieval: {result.timings.retrieval_ms}ms</span>
            <span>Generation: {result.timings.generation_ms}ms</span>
            <span>Total: {result.timings.total_ms}ms</span>
            {result.tokens_used && (
              <span>Tokens: {result.tokens_used.input_tokens} in / {result.tokens_used.output_tokens} out</span>
            )}
          </div>
        )}
      </div>

      {/* Low confidence warning */}
      {lowConfidence && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-start gap-3">
          <svg className="h-5 w-5 text-amber-500 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <div>
            <p className="text-sm font-medium text-amber-800">Low confidence</p>
            <p className="text-sm text-amber-600">All retrieved chunks scored below 0.4. The answer may not be in the document.</p>
          </div>
        </div>
      )}

      {/* Sources */}
      {sources.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
              Sources ({sources.length} chunks)
            </h3>
            <CopyButton text={sourcesText} label="Copy Sources" />
          </div>

          <div className="space-y-3">
            {sources.map((source, i) => (
              <div
                key={source.chunk_id || i}
                onClick={() => setSelectedChunk(source)}
                className="border border-gray-200 rounded-lg p-4 cursor-pointer hover:border-blue-300 hover:bg-blue-50/30 transition-colors"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="inline-block bg-blue-100 text-blue-800 text-xs font-medium px-2 py-0.5 rounded">
                      Page {source.page_num}
                    </span>
                    {source.doc_id && (
                      <span className="text-xs text-gray-400">{source.doc_id}</span>
                    )}
                  </div>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded ${scoreLabel(source.score)}`}>
                    {(source.score * 100).toFixed(0)}%
                  </span>
                </div>

                <p className="text-sm text-gray-600 line-clamp-3">
                  {source.text}
                </p>

                {/* Relevance bar */}
                <div className="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${scoreColor(source.score)}`}
                    style={{ width: `${Math.max(source.score * 100, 2)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {selectedChunk && (
        <ChunkModal chunk={selectedChunk} onClose={() => setSelectedChunk(null)} />
      )}
    </section>
  )
}

export default ResultsSection
