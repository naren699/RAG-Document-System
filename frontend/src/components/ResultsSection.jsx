import { useState } from 'react'
import ChunkModal from './ChunkModal'
import CopyButton from './CopyButton'

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

function FormattedAnswer({ text }) {
  if (!text) return null
  const lines = text.split('\n')
  let inList = false
  const elements = []

  lines.forEach((line, i) => {
    const bulletMatch = line.match(/^[\s]*[*\-]\s+(.*)/)
    if (bulletMatch) {
      if (!inList) { inList = true }
      elements.push({ type: 'li', content: bulletMatch[1], key: i })
    } else {
      if (inList) { inList = false }
      if (line.trim()) {
        elements.push({ type: 'p', content: line, key: i })
      } else {
        elements.push({ type: 'br', key: i })
      }
    }
  })

  const formatInline = (str) => {
    const parts = []
    const regex = /\*\*(.+?)\*\*/g
    let last = 0
    let match
    while ((match = regex.exec(str)) !== null) {
      if (match.index > last) parts.push(str.slice(last, match.index))
      parts.push(<strong key={match.index} className="font-semibold">{match[1]}</strong>)
      last = regex.lastIndex
    }
    if (last < str.length) parts.push(str.slice(last))
    return parts.length ? parts : str
  }

  const rendered = []
  let listItems = []

  elements.forEach((el) => {
    if (el.type === 'li') {
      listItems.push(<li key={el.key} className="ml-1">{formatInline(el.content)}</li>)
    } else {
      if (listItems.length) {
        rendered.push(<ul key={`ul-${el.key}`} className="list-disc pl-5 my-2 space-y-1">{listItems}</ul>)
        listItems = []
      }
      if (el.type === 'p') {
        rendered.push(<p key={el.key} className="mb-2 last:mb-0">{formatInline(el.content)}</p>)
      }
    }
  })
  if (listItems.length) {
    rendered.push(<ul key="ul-end" className="list-disc pl-5 my-2 space-y-1">{listItems}</ul>)
  }

  return <div>{rendered}</div>
}

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

function ResultsSection({ result, query }) {
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

        <div className="bg-gray-50 rounded-lg p-4 text-gray-800 leading-relaxed">
          <FormattedAnswer text={result.answer} />
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
                  <div className="flex items-center gap-2">
                    <CopyButton text={`Page ${source.page_num}: ${source.text}`} label="Copy" />
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${scoreLabel(source.score)}`}>
                      {(source.score * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>

                <p className="text-sm text-gray-600 line-clamp-3">
                  <HighlightedText text={source.text} query={query} />
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
        <ChunkModal chunk={selectedChunk} query={query} onClose={() => setSelectedChunk(null)} />
      )}
    </section>
  )
}

export default ResultsSection
