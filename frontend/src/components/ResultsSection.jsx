import { useState, useMemo, useRef, useEffect } from 'react'
import { CheckCircle2, AlertTriangle, SearchX, ChevronDown, Copy, Check, ThumbsUp, ThumbsDown, Download, Shield, ShieldAlert, ShieldX, Clock, FileText, Eye, Image as ImageIcon, Info } from 'lucide-react'
import HighlightedText, { extractQueryKeywords } from './HighlightedText'
import { pluralize } from '../utils/pluralize'

function parseCitations(text) {
  const cited = new Set()
  let match
  const regex = /\[(\d+)\]/g
  while ((match = regex.exec(text)) !== null) cited.add(parseInt(match[1], 10))
  return cited
}

function scoreLevel(score) {
  if (score >= 4) return { label: 'High', cls: 'text-[var(--color-success)] bg-[var(--color-success-subtle)]' }
  if (score >= 1) return { label: 'Medium', cls: 'text-[var(--color-warning)] bg-[var(--color-warning-subtle)]' }
  return { label: 'Low', cls: 'text-[var(--color-danger)] bg-[var(--color-danger-subtle)]' }
}

function sigmoidPercent(score) {
  return Math.max(Math.min(100 / (1 + Math.exp(-score)), 100), 3)
}

function barColor(score) {
  if (score >= 4) return 'bg-[var(--color-success)]'
  if (score >= 1) return 'bg-[var(--color-warning)]'
  return 'bg-[var(--color-danger)]'
}

function CopyBtn({ text, className = '' }) {
  const [copied, setCopied] = useState(false)
  const copy = async (e) => {
    e.stopPropagation()
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button onClick={copy} className={`p-1.5 rounded-[var(--radius-btn)] hover:bg-[var(--color-surface-tertiary)] transition-theme ${className}`} aria-label="Copy" title="Copy">
      {copied ? <Check size={14} className="text-[var(--color-success)]" /> : <Copy size={14} className="text-[var(--color-text-tertiary)]" />}
    </button>
  )
}

function FormattedAnswer({ text, onCitationClick, sourceSnippets }) {
  if (!text) return null
  const lines = text.split('\n')
  const elements = []

  lines.forEach((line, i) => {
    const bulletMatch = line.match(/^[\s]*[*-]\s+(.*)/)
    if (bulletMatch) {
      elements.push({ type: 'li', content: bulletMatch[1], key: i })
    } else if (line.trim()) {
      elements.push({ type: 'p', content: line, key: i })
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
        const snippet = sourceSnippets?.[num]
        parts.push(
          <button
            key={`c-${match.index}`}
            onClick={() => onCitationClick?.(num)}
            className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 mx-0.5 text-[11px] font-bold text-[var(--color-accent)] bg-[var(--color-accent-subtle)] rounded hover:bg-[var(--color-accent)]/20 transition-theme align-super cursor-pointer"
            title={snippet ? `[${num}] ${snippet.slice(0, 120)}...` : `Source ${num}`}
            aria-label={`Citation ${num}`}
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
      if (listItems.length) { rendered.push(<ul key={`ul-${el.key}`} className="list-disc pl-5 my-2 space-y-1">{listItems}</ul>); listItems = [] }
      if (el.type === 'p') rendered.push(<p key={el.key} className="mb-2 last:mb-0">{formatInline(el.content)}</p>)
    }
  })
  if (listItems.length) rendered.push(<ul key="ul-end" className="list-disc pl-5 my-2 space-y-1">{listItems}</ul>)
  return <div>{rendered}</div>
}

function getRelevantSnippet(text, query, maxLen = 350) {
  if (!text || text.length <= maxLen) return text
  const keywords = extractQueryKeywords(query)
  if (!keywords.length) return text.slice(0, maxLen) + '...'

  const sentences = text.split(/(?<=[.!?\n])\s+/)
  let bestIdx = 0, bestScore = 0
  for (let i = 0; i < sentences.length; i++) {
    const lower = sentences[i].toLowerCase()
    let score = 0
    for (const kw of keywords) { if (lower.includes(kw.toLowerCase())) score++ }
    if (score > bestScore) { bestScore = score; bestIdx = i }
  }

  if (bestScore === 0) {
    const lowerText = text.toLowerCase()
    for (const kw of keywords) {
      const idx = lowerText.indexOf(kw.toLowerCase())
      if (idx !== -1) {
        const hw = Math.floor(maxLen / 2)
        let s = Math.max(0, idx - hw), e = Math.min(text.length, s + maxLen)
        if (e - s < maxLen) s = Math.max(0, e - maxLen)
        return (s > 0 ? '...' : '') + text.slice(s, e) + (e < text.length ? '...' : '')
      }
    }
    return text.slice(0, maxLen) + '...'
  }

  let result = sentences[bestIdx], lo = bestIdx - 1, hi = bestIdx + 1
  while (result.length < maxLen) {
    let added = false
    if (hi < sentences.length && result.length + sentences[hi].length < maxLen + 50) { result += ' ' + sentences[hi]; hi++; added = true }
    if (lo >= 0 && result.length + sentences[lo].length < maxLen + 50) { result = sentences[lo] + ' ' + result; lo--; added = true }
    if (!added) break
  }
  return (bestIdx > 0 ? '...' : '') + result + (hi < sentences.length ? '...' : '')
}

function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

function GroundingBadge({ grounding }) {
  if (!grounding) return null
  const g = grounding.grounded_claims ?? grounding.grounded_sentences ?? 0
  const t = grounding.total_claims ?? grounding.total_sentences ?? 0
  const score = grounding.score

  let Icon, label, cls
  if (score >= 0.7) { Icon = Shield; label = 'Grounded'; cls = 'text-[var(--color-success)] bg-[var(--color-success-subtle)]' }
  else if (score >= 0.4) { Icon = ShieldAlert; label = 'Partially grounded'; cls = 'text-[var(--color-warning)] bg-[var(--color-warning-subtle)]' }
  else { Icon = ShieldX; label = 'Low confidence'; cls = 'text-[var(--color-danger)] bg-[var(--color-danger-subtle)]' }

  return (
    <span
      className={`inline-flex items-center gap-1 text-[12px] font-medium px-2 py-0.5 rounded-full ${cls}`}
      title="Automatic estimate of whether the answer matches the retrieved text. It does not prove the answer is correct."
    >
      <Icon size={12} />
      {g}/{t} claims
    </span>
  )
}

function StatusBadge({ result }) {
  if (result.is_not_found) {
    return (
      <span className="inline-flex items-center gap-1.5 text-[12px] font-medium text-[var(--color-accent)] bg-[var(--color-accent-subtle)] px-2 py-0.5 rounded-full">
        <SearchX size={12} /> Not in document
      </span>
    )
  }
  if (result.grounding?.score < 0.4) {
    return (
      <span className="inline-flex items-center gap-1.5 text-[12px] font-medium text-[var(--color-warning)] bg-[var(--color-warning-subtle)] px-2 py-0.5 rounded-full">
        <AlertTriangle size={12} /> Low confidence
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-[12px] font-medium text-[var(--color-success)] bg-[var(--color-success-subtle)] px-2 py-0.5 rounded-full">
      <CheckCircle2 size={12} /> Answered
    </span>
  )
}

function ScoreBreakdown({ source }) {
  const [open, setOpen] = useState(false)
  const scores = [
    { label: 'Dense', value: source.dense_score, max: 1 },
    { label: 'BM25', value: source.bm25_score, max: 20 },
    { label: 'RRF', value: source.rrf_score, max: 0.033 },
    { label: 'Rerank', value: source.rerank_score, max: 10 },
  ].filter(s => s.value != null)

  if (!scores.length) return null

  return (
    <div>
      <button
        onClick={(e) => { e.stopPropagation(); setOpen(!open) }}
        className="flex items-center gap-1 text-[11px] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)] transition-theme mt-1"
      >
        <ChevronDown size={12} className={`transition-transform duration-150 ${open ? 'rotate-180' : ''}`} />
        Score breakdown
      </button>
      {open && (
        <div className="mt-2 space-y-1.5">
          {scores.map(s => {
            const pct = Math.max(Math.min((s.value / s.max) * 100, 100), 2)
            return (
              <div key={s.label} className="flex items-center gap-2">
                <span className="text-[11px] text-[var(--color-text-tertiary)] w-12 shrink-0">{s.label}</span>
                <div className="flex-1 h-1.5 bg-[var(--color-surface-tertiary)] rounded-full overflow-hidden">
                  <div className="h-full bg-[var(--color-accent)] rounded-full" style={{ width: `${pct}%` }} />
                </div>
                <span className="text-[11px] text-[var(--color-text-tertiary)] w-12 text-right tabular-nums">{s.value.toFixed(s.max < 1 ? 4 : 2)}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function SourceCard({ source, index, query, isCited, isUncited, expanded, onToggleExpand }) {
  const cardRef = useRef(null)
  const [flash, setFlash] = useState(false)
  const sl = scoreLevel(source.rerank_score ?? source.score ?? 0)

  useEffect(() => {
    if (flash) { const t = setTimeout(() => setFlash(false), 1000); return () => clearTimeout(t) }
  }, [flash])

  const scrollAndFlash = () => {
    cardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setFlash(true)
  }

  return (
    <div
      ref={cardRef}
      id={`source-${index + 1}`}
      data-scroll-flash={scrollAndFlash}
      className={`rounded-[var(--radius-card)] border p-4 transition-all duration-200 ${
        flash ? 'ring-2 ring-[var(--color-accent)]' :
        isCited ? 'border-[var(--color-success)]/30 bg-[var(--color-success-subtle)]' :
        isUncited ? 'border-[var(--color-border)] opacity-60' :
        'border-[var(--color-border)] bg-[var(--color-surface)]'
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <span className="inline-flex items-center justify-center w-6 h-6 text-[11px] font-bold text-[var(--color-text-inverse)] bg-[var(--color-text-secondary)] rounded shrink-0">
            {index + 1}
          </span>
          {source.doc_id && (
            <span className="text-[12px] text-[var(--color-text-secondary)] truncate max-w-[120px]">{source.doc_id}</span>
          )}
          <span className="text-[12px] text-[var(--color-accent)] font-medium">
            Page {source.page_num}{source.section_title ? ` · ${source.section_title}` : ''}
          </span>
          {source.page_type && source.page_type !== 'text' && (
            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-purple-600 bg-purple-100 dark:bg-purple-900/30 dark:text-purple-400 px-1.5 py-0.5 rounded">
              <ImageIcon size={10} /> Visual
            </span>
          )}
          {isCited && (
            <span className="text-[11px] font-medium text-[var(--color-success)] bg-[var(--color-success-subtle)] px-1.5 py-0.5 rounded">Cited</span>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <CopyBtn text={source.text} />
          <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${sl.cls}`} title={`Rerank score: ${(source.rerank_score ?? source.score)?.toFixed(3)}`}>
            {sl.label}
          </span>
        </div>
      </div>

      {/* Snippet */}
      <div className="text-[14px] text-[var(--color-text-secondary)] leading-relaxed">
        {expanded ? (
          <HighlightedText text={source.text} query={query} />
        ) : (
          <HighlightedText text={getRelevantSnippet(source.text, query)} query={query} />
        )}
      </div>
      {source.text.length > 350 && (
        <button
          onClick={(e) => { e.stopPropagation(); onToggleExpand() }}
          className="text-[12px] text-[var(--color-accent)] hover:underline mt-1"
        >
          {expanded ? 'Show less' : 'Show full chunk'}
        </button>
      )}

      {/* Score breakdown */}
      <ScoreBreakdown source={source} />

      {/* Visual page thumbnail */}
      {source.image_path && (
        <img
          src={`http://localhost:8000/${source.image_path}`}
          alt={`Page ${source.page_num}`}
          className="mt-3 max-w-full max-h-40 rounded-[var(--radius-btn)] border border-[var(--color-border)] cursor-pointer hover:opacity-90"
          loading="lazy"
          onClick={(e) => { e.stopPropagation(); window.open(`http://localhost:8000/${source.image_path}`, '_blank') }}
        />
      )}
    </div>
  )
}

function DetailsTable({ timings, tokens, cost, sources, citedCount }) {
  if (!timings) return null
  const rows = []
  if (timings.embed_query_ms != null) rows.push(['Embed', `${timings.embed_query_ms}ms`])
  if (timings.dense_search_ms != null) rows.push(['Dense search', `${timings.dense_search_ms}ms`])
  if (timings.bm25_search_ms != null) rows.push(['BM25 search', `${timings.bm25_search_ms}ms`])
  if (timings.rerank_ms != null) rows.push(['Rerank', `${timings.rerank_ms}ms`])
  if (timings.retrieval_total_ms != null) rows.push(['Retrieval total', `${timings.retrieval_total_ms}ms`])
  if (timings.time_to_first_token_ms != null) rows.push(['Time to first token', `${timings.time_to_first_token_ms}ms`])
  if (timings.generation_ms != null) rows.push(['Generation', `${timings.generation_ms}ms`])
  if (timings.candidates_total != null) rows.push(['Retrieved / kept', `${timings.candidates_total} / ${timings.candidates_kept ?? '?'}`])
  const contextTokens = sources?.reduce((sum, s) => sum + (s.token_count || 0), 0)
  if (contextTokens > 0) rows.push(['Context', `${contextTokens} tokens, ${pluralize(sources.length, 'chunk')}, ${citedCount} cited`])
  if (tokens) {
    const est = tokens.estimated ? ' (est.)' : ''
    rows.push(['Tokens', `${tokens.input_tokens?.toLocaleString()}${est} in / ${tokens.output_tokens?.toLocaleString()} out`])
  }
  if (tokens?.reasoning_tokens > 0) rows.push(['Reasoning', `${tokens.reasoning_tokens} tokens`])
  if (cost != null) rows.push(['Cost', `~$${cost < 0.01 ? cost.toFixed(5) : cost.toFixed(3)}`])

  return (
    <div className="mt-3 rounded-[var(--radius-btn)] bg-[var(--color-surface-secondary)] border border-[var(--color-border)] overflow-hidden">
      <table className="w-full text-[12px]">
        <tbody>
          {rows.map(([label, value], i) => (
            <tr key={i} className={i % 2 === 0 ? '' : 'bg-[var(--color-surface-tertiary)]/50'}>
              <td className="px-3 py-1.5 text-[var(--color-text-tertiary)] font-medium whitespace-nowrap">{label}</td>
              <td className="px-3 py-1.5 text-[var(--color-text-secondary)] text-right tabular-nums">{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ResultsSection({ result, query, isStreaming, onFeedback }) {
  const [showDetails, setShowDetails] = useState(false)
  const [showExport, setShowExport] = useState(false)
  const [expandedSources, setExpandedSources] = useState(new Set())
  const [showUncited, setShowUncited] = useState(false)
  const [feedbackGiven, setFeedbackGiven] = useState(null)

  const sources = result.sources || []
  const citedIndices = useMemo(() => parseCitations(result.answer || ''), [result.answer])
  const citedSources = sources.filter((_, i) => citedIndices.has(i + 1))
  const uncitedSources = sources.filter((_, i) => !citedIndices.has(i + 1))

  const sourceSnippets = useMemo(() => {
    const map = {}
    sources.forEach((s, i) => { map[i + 1] = getRelevantSnippet(s.text, query, 120) })
    return map
  }, [sources, query])

  const handleCitationClick = (num) => {
    const el = document.getElementById(`source-${num}`)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      const fn = el.dataset.scrollFlash
      if (typeof el.__scrollFlash === 'function') el.__scrollFlash()
    }
  }

  const [showFeedbackPopover, setShowFeedbackPopover] = useState(false)
  const [feedbackReason, setFeedbackReason] = useState('')
  const [feedbackOther, setFeedbackOther] = useState('')

  const handleFeedback = (rating, reason) => {
    setFeedbackGiven(rating)
    setShowFeedbackPopover(false)
    onFeedback?.(rating, reason)
  }

  const summaryParts = []
  if (result.timings?.total_ms != null) summaryParts.push(`${(result.timings.total_ms / 1000).toFixed(1)}s`)
  if (result.tokens_used) {
    const t = result.tokens_used
    summaryParts.push(`${((t.input_tokens || 0) + (t.output_tokens || 0)).toLocaleString()} tokens`)
  }
  if (result.estimated_cost_usd != null) summaryParts.push(`~$${result.estimated_cost_usd < 0.01 ? result.estimated_cost_usd.toFixed(5) : result.estimated_cost_usd.toFixed(3)}`)

  // ── Not in document card ──
  if (result.is_not_found) {
    return (
      <div className="space-y-4">
        <div className="rounded-[var(--radius-card)] border border-[var(--color-accent)]/30 bg-[var(--color-accent-subtle)] p-6 shadow-[var(--shadow-card)]">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-[var(--color-accent)]/10 flex items-center justify-center shrink-0 mt-0.5">
              <SearchX size={18} className="text-[var(--color-accent)]" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <StatusBadge result={result} />
              </div>
              <p className="text-[16px] text-[var(--color-text-primary)] font-medium">
                This information wasn't found in the uploaded documents.
              </p>
              <p className="text-[14px] text-[var(--color-text-secondary)] mt-2">
                The search looked through all available chunks but none passed the relevance threshold.
              </p>
              <div className="mt-4 p-3 rounded-[var(--radius-btn)] bg-[var(--color-surface)] border border-[var(--color-border)]">
                <p className="text-[12px] text-[var(--color-text-tertiary)] font-medium mb-1">Try next</p>
                <ul className="text-[13px] text-[var(--color-text-secondary)] space-y-1">
                  <li>- Rephrase your question with different keywords</li>
                  <li>- Lower the score threshold in Settings</li>
                  <li>- Check if the information is in a different document</li>
                </ul>
              </div>
              {summaryParts.length > 0 && (
                <p className="text-[12px] text-[var(--color-text-tertiary)] mt-3">{summaryParts.join(' · ')}</p>
              )}
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ── Answered / Low confidence card ──
  return (
    <div className="space-y-4">
      {/* Answer card */}
      <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-[var(--shadow-card)]">
        {/* Header row */}
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <StatusBadge result={result} />
            <GroundingBadge grounding={result.grounding} />
          </div>
          {result.provider && result.provider !== 'none' && (
            <span className="text-[11px] text-[var(--color-text-tertiary)]">{result.provider}/{result.model}</span>
          )}
        </div>

        {result.rewritten_query && (
          <p className="text-[12px] text-[var(--color-text-tertiary)] mb-2 italic">
            Interpreted as: {result.rewritten_query}
          </p>
        )}

        {/* Answer text */}
        <div className="text-[16px] text-[var(--color-text-primary)] leading-relaxed" aria-live="polite">
          <FormattedAnswer text={result.answer} onCitationClick={handleCitationClick} sourceSnippets={sourceSnippets} />
          {isStreaming && (
            <span className="inline-block w-2 h-5 bg-[var(--color-accent)] animate-pulse ml-0.5 align-text-bottom rounded-sm" />
          )}
        </div>

        {/* Low confidence warning */}
        {!isStreaming && result.grounding?.score < 0.4 && result.grounding?.score > 0 && (
          <div className="flex items-start gap-2 mt-4 p-3 rounded-[var(--radius-btn)] bg-[var(--color-warning-subtle)] border border-[var(--color-warning)]/20">
            <AlertTriangle size={14} className="text-[var(--color-warning)] shrink-0 mt-0.5" />
            <p className="text-[13px] text-[var(--color-warning)]">
              Some claims may not be supported by the retrieved text. Try rephrasing, or raise Top-K in Settings.
            </p>
          </div>
        )}

        {/* Actions row */}
        {!isStreaming && (
          <div className="flex items-center justify-between mt-4 pt-3 border-t border-[var(--color-border)]">
            <div className="flex items-center gap-1">
              {/* Feedback */}
              <button
                onClick={() => handleFeedback('up')}
                className={`p-1.5 rounded-[var(--radius-btn)] transition-theme ${
                  feedbackGiven === 'up' ? 'bg-[var(--color-success-subtle)] text-[var(--color-success)]' : 'text-[var(--color-text-tertiary)] hover:text-[var(--color-success)] hover:bg-[var(--color-surface-tertiary)]'
                }`}
                aria-label="Thumbs up — helpful answer"
              >
                <ThumbsUp size={15} />
              </button>
              <div className="relative">
                <button
                  onClick={() => {
                    if (feedbackGiven === 'down') return
                    setShowFeedbackPopover(!showFeedbackPopover)
                  }}
                  className={`p-1.5 rounded-[var(--radius-btn)] transition-theme ${
                    feedbackGiven === 'down' ? 'bg-[var(--color-danger-subtle)] text-[var(--color-danger)]' : 'text-[var(--color-text-tertiary)] hover:text-[var(--color-danger)] hover:bg-[var(--color-surface-tertiary)]'
                  }`}
                  aria-label="Thumbs down — report issue"
                >
                  <ThumbsDown size={15} />
                </button>
                {showFeedbackPopover && (
                  <div className="absolute bottom-full left-0 mb-2 w-64 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-card)] shadow-[var(--shadow-popover)] p-3 z-20 space-y-2">
                    <p className="text-[12px] font-medium text-[var(--color-text-primary)]">What went wrong?</p>
                    {[
                      { key: 'wrong', label: 'Wrong answer' },
                      { key: 'not_in_doc', label: 'Answered but not in document' },
                      { key: 'missing', label: 'Missing information' },
                      { key: 'other', label: 'Other' },
                    ].map(opt => (
                      <label key={opt.key} className="flex items-center gap-2 text-[13px] text-[var(--color-text-secondary)] cursor-pointer hover:text-[var(--color-text-primary)]">
                        <input
                          type="radio" name="feedback-reason" value={opt.key}
                          checked={feedbackReason === opt.key}
                          onChange={() => setFeedbackReason(opt.key)}
                          className="accent-[var(--color-danger)]"
                        />
                        {opt.label}
                      </label>
                    ))}
                    {feedbackReason === 'other' && (
                      <input
                        type="text" placeholder="Tell us more..."
                        value={feedbackOther}
                        onChange={(e) => setFeedbackOther(e.target.value)}
                        className="w-full border border-[var(--color-border)] bg-[var(--color-surface)] text-[13px] text-[var(--color-text-primary)] rounded-[var(--radius-input)] px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
                      />
                    )}
                    <div className="flex justify-end gap-2 pt-1">
                      <button
                        onClick={() => setShowFeedbackPopover(false)}
                        className="text-[12px] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleFeedback('down', feedbackReason === 'other' ? feedbackOther || 'other' : feedbackReason)}
                        disabled={!feedbackReason}
                        className="text-[12px] font-medium text-[var(--color-text-inverse)] bg-[var(--color-danger)] px-3 py-1 rounded-[var(--radius-btn)] hover:bg-red-700 disabled:opacity-50"
                      >
                        Submit
                      </button>
                    </div>
                  </div>
                )}
              </div>

              <div className="w-px h-4 bg-[var(--color-border)] mx-1" />

              <CopyBtn text={result.answer} />

              {/* Export menu */}
              <div className="relative">
                <button
                  onClick={() => setShowExport(!showExport)}
                  className="p-1.5 rounded-[var(--radius-btn)] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-tertiary)] transition-theme"
                  aria-label="Export"
                >
                  <Download size={15} />
                </button>
                {showExport && (
                  <div className="absolute bottom-full left-0 mb-1 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-btn)] shadow-[var(--shadow-popover)] py-1 min-w-[100px] z-10">
                    {[
                      { label: 'JSON', fn: () => downloadFile(JSON.stringify({ query, ...result }, null, 2), 'fare-answer.json', 'application/json') },
                      { label: 'Text', fn: () => downloadFile(`Q: ${query}\n\n${result.answer}\n\nSources:\n${sources.map((s, i) => `[${i + 1}] ${s.text}`).join('\n\n')}`, 'fare-answer.txt', 'text/plain') },
                      { label: 'Markdown', fn: () => downloadFile(`# ${query}\n\n${result.answer}\n\n## Sources\n\n${sources.map((s, i) => `### [${i + 1}] Page ${s.page_num}\n\n${s.text}`).join('\n\n')}`, 'fare-answer.md', 'text/markdown') },
                    ].map(item => (
                      <button key={item.label} onClick={() => { item.fn(); setShowExport(false) }} className="w-full text-left px-3 py-1.5 text-[13px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-tertiary)] transition-theme">
                        {item.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Summary line */}
            <span className="text-[12px] text-[var(--color-text-tertiary)] tabular-nums">
              {summaryParts.join(' · ')}
            </span>
          </div>
        )}

        {/* Details toggle */}
        {!isStreaming && result.timings && (
          <div>
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="flex items-center gap-1 mt-2 text-[12px] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)] transition-theme"
            >
              <ChevronDown size={12} className={`transition-transform duration-150 ${showDetails ? 'rotate-180' : ''}`} />
              Details
            </button>
            {showDetails && (
              <DetailsTable timings={result.timings} tokens={result.tokens_used} cost={result.estimated_cost_usd} sources={sources} citedCount={citedSources.length} />
            )}
          </div>
        )}
      </div>

      {/* Sources */}
      {sources.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-[14px] font-semibold text-[var(--color-text-primary)]">
              Sources
              <span className="text-[var(--color-text-tertiary)] font-normal ml-1">
                ({pluralize(sources.length, 'chunk')}{citedSources.length > 0 ? `, ${citedSources.length} cited` : ''})
              </span>
            </h3>
          </div>

          {sources.map((source, i) => {
            const isCited = citedIndices.has(i + 1)
            const isUncited = !isCited && citedIndices.size > 0
            if (isUncited && !showUncited) return null

            return (
              <SourceCard
                key={source.chunk_id || i}
                source={source}
                index={i}
                query={query}
                isCited={isCited}
                isUncited={isUncited}
                expanded={expandedSources.has(i)}
                onToggleExpand={() => setExpandedSources(prev => {
                  const next = new Set(prev)
                  next.has(i) ? next.delete(i) : next.add(i)
                  return next
                })}
              />
            )
          })}

          {uncitedSources.length > 0 && citedIndices.size > 0 && (
            <button
              onClick={() => setShowUncited(!showUncited)}
              className="w-full text-center py-2 text-[13px] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)] transition-theme"
            >
              {showUncited
                ? `Hide ${uncitedSources.length} uncited source${uncitedSources.length > 1 ? 's' : ''}`
                : `Show ${uncitedSources.length} more source${uncitedSources.length > 1 ? 's' : ''} (not cited)`}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default ResultsSection
