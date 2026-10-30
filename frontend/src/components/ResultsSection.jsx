import { useState, useMemo } from 'react'
import ChunkModal from './ChunkModal'
import CopyButton from './CopyButton'
import HighlightedText, { extractQueryKeywords } from './HighlightedText'
import { pluralize } from '../utils/pluralize'

function scoreColor(score) {
  if (score >= 4) return 'bg-green-500'
  if (score >= 1) return 'bg-yellow-500'
  return 'bg-red-400'
}

function scoreLabel(score) {
  if (score >= 4) return 'text-green-700 bg-green-50'
  if (score >= 1) return 'text-yellow-700 bg-yellow-50'
  return 'text-red-700 bg-red-50'
}

function parseCitations(text) {
  const cited = new Set()
  const regex = /\[(\d+)\]/g
  let match
  while ((match = regex.exec(text)) !== null) {
    cited.add(parseInt(match[1], 10))
  }
  return cited
}

function FormattedAnswer({ text, onCitationClick }) {
  if (!text) return null
  const lines = text.split('\n')
  let inList = false
  const elements = []

  lines.forEach((line, i) => {
    const bulletMatch = line.match(/^[\s]*[*-]\s+(.*)/)
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
    const regex = /(\*\*(.+?)\*\*|\[(\d+)\])/g
    let last = 0
    let match
    while ((match = regex.exec(str)) !== null) {
      if (match.index > last) parts.push(str.slice(last, match.index))
      if (match[2]) {
        parts.push(<strong key={`b-${match.index}`} className="font-semibold">{match[2]}</strong>)
      } else if (match[3]) {
        const num = parseInt(match[3], 10)
        parts.push(
          <button
            key={`c-${match.index}`}
            onClick={() => onCitationClick?.(num)}
            className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 mx-0.5 text-xs font-semibold text-blue-700 bg-blue-100 rounded hover:bg-blue-200 transition-colors align-super cursor-pointer"
            title={`Source ${num}`}
          >
            {num}
          </button>
        )
      }
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

function groundingColor(score) {
  if (score >= 0.7) return 'text-green-700 bg-green-50'
  if (score >= 0.4) return 'text-yellow-700 bg-yellow-50'
  return 'text-red-700 bg-red-50'
}

function TimingsDetail({ timings, tokens, cost, grounding, sources, citedCount }) {
  if (!timings) return null

  const items = []
  if (timings.embed_query_ms != null) items.push(`Embed: ${timings.embed_query_ms}ms`)
  if (timings.dense_search_ms != null) items.push(`Dense: ${timings.dense_search_ms}ms`)
  if (timings.bm25_search_ms != null) items.push(`BM25: ${timings.bm25_search_ms}ms`)
  if (timings.rerank_ms != null) items.push(`Rerank: ${timings.rerank_ms}ms`)
  if (timings.retrieval_total_ms != null) items.push(`Retrieval: ${timings.retrieval_total_ms}ms`)
  if (timings.time_to_first_token_ms != null) items.push(`TTFT: ${timings.time_to_first_token_ms}ms`)
  if (timings.generation_ms != null) items.push(`Generation: ${timings.generation_ms}ms`)
  if (timings.total_ms != null) items.push(`Total: ${timings.total_ms}ms`)

  const contextTokens = sources?.reduce((sum, s) => sum + (s.token_count || 0), 0)

  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-xs text-gray-400">
      {items.map((item, i) => <span key={i}>{item}</span>)}
      {timings.candidates_total != null && (
        <span>Retrieved {timings.candidates_total}, kept {timings.candidates_kept ?? sources?.length ?? '?'}</span>
      )}
      {tokens && (
        <span>Tokens: {tokens.input_tokens?.toLocaleString()} in / {tokens.output_tokens?.toLocaleString()} out{tokens.estimated ? ' (estimated)' : ''}</span>
      )}
      {tokens?.reasoning_tokens > 0 && (
        <span>Reasoning: {tokens.reasoning_tokens}</span>
      )}
      {cost != null && (
        <span>Cost: ~${cost < 0.01 ? cost.toFixed(5) : cost.toFixed(3)}</span>
      )}
      {grounding && (
        <span className={`px-1.5 py-0.5 rounded font-medium ${groundingColor(grounding.score)}`}>
          Grounded: {grounding.grounded_claims ?? grounding.grounded_sentences}/{grounding.total_claims ?? grounding.total_sentences} claims
        </span>
      )}
      {grounding?.invalid_citations?.length > 0 && (
        <span className="text-red-500">Invalid citations: [{grounding.invalid_citations.join(', ')}]</span>
      )}
      {contextTokens > 0 && (
        <span>Context: {contextTokens} tokens, {pluralize(sources.length, 'chunk')}, {citedCount} cited</span>
      )}
    </div>
  )
}

function getRelevantSnippet(text, query, maxLen = 400) {
  if (!text || text.length <= maxLen) return text
  const keywords = extractQueryKeywords(query)
  if (!keywords.length) return text.slice(0, maxLen) + '...'

  const lowerText = text.toLowerCase()
  const sentences = text.split(/(?<=[.!?\n])\s+/)
  let bestSentIdx = 0
  let bestScore = 0

  for (let i = 0; i < sentences.length; i++) {
    const lower = sentences[i].toLowerCase()
    let score = 0
    for (const kw of keywords) {
      if (lower.includes(kw.toLowerCase())) score++
    }
    if (score > bestScore) {
      bestScore = score
      bestSentIdx = i
    }
  }

  if (bestScore === 0) {
    for (const kw of keywords) {
      const idx = lowerText.indexOf(kw.toLowerCase())
      if (idx !== -1) {
        const halfWindow = Math.floor(maxLen / 2)
        let start = Math.max(0, idx - halfWindow)
        let end = Math.min(text.length, start + maxLen)
        if (end - start < maxLen) start = Math.max(0, end - maxLen)
        let snippet = text.slice(start, end)
        if (start > 0) snippet = '...' + snippet
        if (end < text.length) snippet = snippet + '...'
        return snippet
      }
    }
    return text.slice(0, maxLen) + '...'
  }

  let result = sentences[bestSentIdx]
  let lo = bestSentIdx - 1
  let hi = bestSentIdx + 1
  while (result.length < maxLen) {
    let added = false
    if (hi < sentences.length && result.length + sentences[hi].length < maxLen + 50) {
      result += ' ' + sentences[hi]
      hi++
      added = true
    }
    if (lo >= 0 && result.length + sentences[lo].length < maxLen + 50) {
      result = sentences[lo] + ' ' + result
      lo--
      added = true
    }
    if (!added) break
  }

  const prefix = lo < bestSentIdx - 1 || bestSentIdx > 0 ? '...' : ''
  const suffix = hi > bestSentIdx + 1 || hi < sentences.length ? '...' : ''
  return prefix + result + suffix
}

function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function ResultsSection({ result, query, isStreaming, onFeedback }) {
  const [selectedChunk, setSelectedChunk] = useState(null)
  const [showUncited, setShowUncited] = useState(false)
  const [expandedSources, setExpandedSources] = useState(new Set())

  const sources = result.sources || []
  const citedIndices = useMemo(() => parseCitations(result.answer || ''), [result.answer])
  const citedSources = sources.filter((_, i) => citedIndices.has(i + 1))
  const uncitedSources = sources.filter((_, i) => !citedIndices.has(i + 1))

  const sourcesText = sources.map((s, i) =>
    `[${i + 1}] Page ${s.page_num} (relevance: ${s.score})\n${s.text}`
  ).join('\n\n')

  const handleCitationClick = (num) => {
    const el = document.getElementById(`source-${num}`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  if (result.is_not_found) {
    return (
      <section className="space-y-6">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
          <div className="flex items-start gap-3">
            <svg className="h-6 w-6 text-blue-500 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="font-medium text-blue-900">Not found in documents</p>
              <p className="text-blue-700 mt-1">{result.answer}</p>
            </div>
          </div>
          <TimingsDetail timings={result.timings} tokens={result.tokens_used} cost={result.estimated_cost_usd} grounding={result.grounding} sources={[]} citedCount={0} />
        </div>
      </section>
    )
  }

  return (
    <section className="space-y-6">
      {/* Answer */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-gray-900">Answer</h2>
            {result.grounding && (
              <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                result.grounding.score >= 0.7 ? 'text-green-700 bg-green-100' :
                result.grounding.score >= 0.4 ? 'text-yellow-700 bg-yellow-100' :
                'text-red-700 bg-red-100'
              }`} title={result.grounding.claims?.map(c => `${c.grounded ? '✓' : '✗'} ${c.text}`).join('\n')}>
                Grounded {result.grounding.grounded_claims ?? result.grounding.grounded_sentences}/{result.grounding.total_claims ?? result.grounding.total_sentences} claims
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {result.provider && result.provider !== 'none' && (
              <span className="text-xs text-gray-400">
                {result.provider}/{result.model}
              </span>
            )}
            <CopyButton text={result.answer} label="Copy" />
            <button
              onClick={() => {
                const md = `# ${query}\n\n${result.answer}\n\n## Sources\n\n${sources.map((s, i) =>
                  `### [${i + 1}] Page ${s.page_num}${s.section_title ? ` — ${s.section_title}` : ''}\n\n${s.text}`
                ).join('\n\n')}`
                downloadFile(md, 'fare-answer.md', 'text/markdown')
              }}
              className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
              title="Download as Markdown"
            >
              MD
            </button>
            <button
              onClick={() => downloadFile(
                JSON.stringify({ query, ...result }, null, 2),
                'fare-answer.json', 'application/json'
              )}
              className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
              title="Download as JSON"
            >
              JSON
            </button>
          </div>
        </div>

        {result.rewritten_query && (
          <p className="text-xs text-gray-400 mb-2">
            Interpreted as: <span className="italic text-gray-500">{result.rewritten_query}</span>
          </p>
        )}

        <div className="bg-gray-50 rounded-lg p-4 text-gray-800 leading-relaxed">
          <FormattedAnswer
            text={result.answer}
            onCitationClick={handleCitationClick}
          />
          {isStreaming && (
            <span className="inline-block w-2 h-4 bg-blue-500 animate-pulse ml-0.5 align-text-bottom" />
          )}
        </div>

        {/* Feedback buttons */}
        {onFeedback && !isStreaming && (
          <div className="flex items-center gap-2 mt-3">
            <span className="text-xs text-gray-400">Helpful?</span>
            <button
              onClick={() => onFeedback('up')}
              className="text-gray-400 hover:text-green-600 transition-colors p-1"
              title="Thumbs up"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 9V5a3 3 0 00-3-3l-4 9v11h11.28a2 2 0 002-1.7l1.38-9a2 2 0 00-2-2.3H14z" />
              </svg>
            </button>
            <button
              onClick={() => onFeedback('down')}
              className="text-gray-400 hover:text-red-600 transition-colors p-1"
              title="Thumbs down"
            >
              <svg className="h-4 w-4 rotate-180" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 9V5a3 3 0 00-3-3l-4 9v11h11.28a2 2 0 002-1.7l1.38-9a2 2 0 00-2-2.3H14z" />
              </svg>
            </button>
          </div>
        )}

        <TimingsDetail timings={result.timings} tokens={result.tokens_used} cost={result.estimated_cost_usd} grounding={result.grounding} sources={sources} citedCount={citedSources.length} />
      </div>

      {/* Sources */}
      {sources.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
              Sources ({pluralize(sources.length, 'chunk')}{citedSources.length > 0 ? `, ${citedSources.length} cited` : ''})
            </h3>
            <CopyButton text={sourcesText} label="Copy Sources" />
          </div>

          <div className="space-y-3">
            {/* Cited sources first */}
            {sources.map((source, i) => {
              const isCited = citedIndices.has(i + 1)
              const isUncited = !isCited && citedIndices.size > 0
              if (isUncited && !showUncited) return null

              return (
                <div
                  key={source.chunk_id || i}
                  id={`source-${i + 1}`}
                  onClick={() => setSelectedChunk(source)}
                  className={`border rounded-lg p-4 cursor-pointer transition-colors ${
                    isCited
                      ? 'border-green-200 bg-green-50/30 hover:border-green-400'
                      : isUncited
                        ? 'border-gray-100 bg-gray-50/50 hover:border-gray-300 opacity-60'
                        : 'border-gray-200 hover:border-blue-300 hover:bg-blue-50/30'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center justify-center w-6 h-6 text-xs font-bold text-white bg-gray-700 rounded">
                        {i + 1}
                      </span>
                      <span className="inline-block bg-blue-100 text-blue-800 text-xs font-medium px-2 py-0.5 rounded">
                        Page {source.page_num}{source.section_title ? ` · ${source.section_title}` : ''}
                      </span>
                      {source.doc_id && (
                        <span className="text-xs text-gray-400">{source.doc_id}</span>
                      )}
                      {isCited && (
                        <span className="text-xs font-medium text-green-700 bg-green-100 px-1.5 py-0.5 rounded">
                          Cited
                        </span>
                      )}
                      {isUncited && (
                        <span className="text-xs text-gray-400 italic">Retrieved</span>
                      )}
                      {source.page_type && source.page_type !== 'text' && (
                        <span className="text-xs font-medium text-purple-700 bg-purple-100 px-1.5 py-0.5 rounded">
                          {source.page_type === 'visual' ? 'Visual' : 'Visual (fallback)'}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <CopyButton text={`Page ${source.page_num}: ${source.text}`} label="Copy" />
                      <span className={`text-xs font-medium px-2 py-0.5 rounded ${scoreLabel(source.rerank_score ?? source.score)}`}
                        title="Cross-encoder rerank score (raw logit)">
                        Rerank: {(source.rerank_score ?? source.score)?.toFixed(2)}
                      </span>
                    </div>
                  </div>

                  <div className="text-sm text-gray-600">
                    {expandedSources.has(i) ? (
                      <HighlightedText text={source.text} query={query} />
                    ) : (
                      <HighlightedText text={getRelevantSnippet(source.text, query)} query={query} />
                    )}
                  </div>
                  {source.text.length > 300 && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setExpandedSources(prev => {
                          const next = new Set(prev)
                          next.has(i) ? next.delete(i) : next.add(i)
                          return next
                        })
                      }}
                      className="text-xs text-blue-600 hover:text-blue-800 mt-1"
                    >
                      {expandedSources.has(i) ? 'Show less' : 'Show more'}
                    </button>
                  )}

                  {/* Relevance bar — sigmoid mapping of raw logit to visual width */}
                  <div className="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${scoreColor(source.rerank_score ?? source.score)}`}
                      style={{ width: `${Math.max(Math.min(100 / (1 + Math.exp(-(source.rerank_score ?? source.score))), 100), 2)}%` }}
                    />
                  </div>

                  {(source.dense_score != null || source.bm25_score != null) && (
                    <div className="flex gap-3 text-[10px] text-gray-400 mt-1">
                      {source.dense_score != null && <span>Dense: {source.dense_score.toFixed(3)}</span>}
                      {source.bm25_score != null && <span>BM25: {source.bm25_score.toFixed(2)}</span>}
                      {source.rrf_score != null && <span>RRF: {source.rrf_score.toFixed(4)}</span>}
                      {source.rerank_score != null && <span>Rerank: {source.rerank_score.toFixed(3)}</span>}
                    </div>
                  )}

                  {source.image_path && (
                    <img
                      src={`http://localhost:8000/${source.image_path}`}
                      alt={`Page ${source.page_num}`}
                      className="mt-2 max-w-full rounded border border-gray-200"
                      loading="lazy"
                    />
                  )}
                </div>
              )
            })}

            {/* Toggle uncited sources */}
            {uncitedSources.length > 0 && citedIndices.size > 0 && (
              <button
                onClick={() => setShowUncited(!showUncited)}
                className="text-sm text-gray-400 hover:text-gray-600 transition-colors w-full text-center py-2"
              >
                {showUncited
                  ? `Hide ${uncitedSources.length} uncited source${uncitedSources.length > 1 ? 's' : ''}`
                  : `Show ${uncitedSources.length} more retrieved source${uncitedSources.length > 1 ? 's' : ''} (not cited)`}
              </button>
            )}
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
