import React, { useState, useRef, useCallback, useEffect } from 'react'
import { Play, Square, Upload, Download, Loader2, CheckCircle2, XCircle, AlertTriangle, Clock, Filter, ShieldAlert, ShieldCheck, Target, BarChart3, Users, Search, Ban, FileText, RefreshCw } from 'lucide-react'
import { pluralize } from '../utils/pluralize'
import MetricCard from './MetricCard'
import ConfusionMatrix from './ConfusionMatrix'

const API = 'http://localhost:8000'

const LABELS = ['Unlabeled', 'Correct', 'Faithful but wrong', 'Hallucinated', 'Correct refusal', 'Wrong refusal']
const LABEL_COLORS = {
  'Correct': 'text-[var(--color-success)]',
  'Faithful but wrong': 'text-[var(--color-warning)]',
  'Hallucinated': 'text-[var(--color-danger)]',
  'Correct refusal': 'text-[var(--color-success)]',
  'Wrong refusal': 'text-[var(--color-danger)]',
}

const METRIC_ICONS = {
  accuracy: Target,
  faithfulness: ShieldCheck,
  answer_relevance: CheckCircle2,
  context_relevance: Search,
  human_agreement_accuracy: Users,
  retrieval_precision_at_k: BarChart3,
  retrieval_recall_at_k: BarChart3,
  refusal_precision: Ban,
  refusal_recall: Ban,
  token_f1: FileText,
  exact_match: FileText,
}

const METRIC_FORMULAS = {
  accuracy: 'correct / total (correct refusal = correct)',
  faithfulness: 'supported claims / total claims',
  answer_relevance: 'relevant answers / total answers',
  context_relevance: 'relevant chunks / retrieved chunks (avg)',
  human_agreement_accuracy: 'matching verdicts / compared verdicts',
  retrieval_precision_at_k: '|retrieved ∩ gold| / k',
  retrieval_recall_at_k: '|retrieved ∩ gold| / |gold|',
  refusal_precision: 'correct refusals / all refusals',
  refusal_recall: 'correct refusals / all unanswerable',
  token_f1: '2 * P * R / (P + R) on normalized tokens',
  exact_match: '1 if normalized prediction == gold',
}

function EvaluateTab() {
  const [testCases, setTestCases] = useState([])
  const [results, setResults] = useState([])
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState(0)
  const [filter, setFilter] = useState('all')
  const [labels, setLabels] = useState({})
  const [summary, setSummary] = useState(null)
  const [expandedClaims, setExpandedClaims] = useState({})
  const [claimsData, setClaimsData] = useState({})

  // Dashboard state
  const [runs, setRuns] = useState([])
  const [selectedRun, setSelectedRun] = useState(null)
  const [dashboardMetrics, setDashboardMetrics] = useState(null)
  const [loadingDashboard, setLoadingDashboard] = useState(false)
  const [startingRun, setStartingRun] = useState(false)

  const stopRef = useRef(false)
  const fileRef = useRef(null)

  const toggleClaims = useCallback((index) => {
    setExpandedClaims(prev => ({ ...prev, [index]: !prev[index] }))
  }, [])

  // Load runs on mount
  useEffect(() => {
    fetchRuns()
  }, [])

  const fetchRuns = async () => {
    try {
      const res = await fetch(`${API}/api/eval/runs`)
      if (res.ok) {
        const data = await res.json()
        setRuns(data.runs || [])
        if (data.runs?.length > 0 && !selectedRun) {
          const latest = data.runs.find(r => r.status === 'completed') || data.runs[0]
          setSelectedRun(latest.run_id)
          loadDashboard(latest.run_id)
        }
      }
    } catch { /* backend not running */ }
  }

  const loadDashboard = async (runId) => {
    if (!runId) return
    setLoadingDashboard(true)
    try {
      const res = await fetch(`${API}/api/eval/runs/${runId}/metrics`)
      if (res.ok) {
        const data = await res.json()
        setDashboardMetrics(data)
      }
    } catch { /* ignore */ }
    setLoadingDashboard(false)
  }

  const startNewRun = async () => {
    setStartingRun(true)
    try {
      const res = await fetch(`${API}/api/eval/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ k: 5, method: 'hybrid' }),
      })
      if (res.ok) {
        const data = await res.json()
        setSelectedRun(data.run_id)
        // Poll for completion
        const poll = setInterval(async () => {
          const r = await fetch(`${API}/api/eval/runs/${data.run_id}`)
          if (r.ok) {
            const rd = await r.json()
            if (rd.status === 'completed' || rd.status === 'failed') {
              clearInterval(poll)
              fetchRuns()
              if (rd.status === 'completed') loadDashboard(data.run_id)
              setStartingRun(false)
            }
          }
        }, 3000)
      }
    } catch { setStartingRun(false) }
  }

  const exportFromServer = async (format) => {
    if (!selectedRun) return
    window.open(`${API}/api/eval/runs/${selectedRun}/export/${format}`, '_blank')
  }

  const loadCSV = (e) => {
    const file = e.target.files[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      const lines = ev.target.result.split('\n').filter(l => l.trim())
      const header = lines[0].split(',').map(h => h.trim().toLowerCase())
      const qi = header.indexOf('query')
      const ei = header.indexOf('expected')
      const si = header.indexOf('should_find')
      if (qi === -1) return

      const cases = lines.slice(1).map(line => {
        const cols = line.split(',').map(c => c.trim())
        return {
          query: cols[qi] || '',
          expected: ei !== -1 ? cols[ei] : '',
          should_find: si !== -1 ? cols[si]?.toLowerCase() !== 'false' : true,
        }
      }).filter(c => c.query)
      setTestCases(cases)
      setResults([])
      setLabels({})
      setSummary(null)
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  const runAll = async () => {
    setRunning(true)
    stopRef.current = false
    setProgress(0)
    const newResults = []

    for (let i = 0; i < testCases.length; i++) {
      if (stopRef.current) break
      const tc = testCases[i]
      const start = Date.now()

      try {
        const res = await fetch(`${API}/api/query`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: tc.query, k: 5, method: 'hybrid', score_threshold: -2.0 }),
        })
        const data = await res.json()
        const latency = Date.now() - start
        const isNotFound = data.is_not_found || false
        const tokens = (data.tokens_used?.input_tokens || 0) + (data.tokens_used?.output_tokens || 0)

        let status = 'unknown'
        if (tc.should_find && !isNotFound) status = 'found'
        else if (tc.should_find && isNotFound) status = 'missed'
        else if (!tc.should_find && isNotFound) status = 'correct_refusal'
        else if (!tc.should_find && !isNotFound) status = 'wrong_answer'

        newResults.push({
          index: i, query: tc.query, expected: tc.expected, should_find: tc.should_find,
          answer: data.answer || '', status, latency, tokens,
          chunks: data.sources?.length || 0, grounding: data.grounding?.score || 0,
        })
      } catch (err) {
        newResults.push({
          index: i, query: tc.query, expected: tc.expected, should_find: tc.should_find,
          answer: '', status: 'error', error: err.message,
          latency: Date.now() - start, tokens: 0, chunks: 0, grounding: 0,
        })
      }

      setResults([...newResults])
      setProgress(Math.round(((i + 1) / testCases.length) * 100))
    }

    const passCount = newResults.filter(r => r.status === 'found' || r.status === 'correct_refusal').length
    const latencies = newResults.filter(r => r.latency).map(r => r.latency)
    const faithScores = newResults.filter(r => r.should_find && r.status === 'found').map(r => r.grounding)
    const abstainCount = newResults.filter(r => !r.should_find).length
    const correctRefusals = newResults.filter(r => r.status === 'correct_refusal').length

    setSummary({
      passRate: newResults.length ? Math.round((passCount / newResults.length) * 100) : 0,
      abstentionRate: abstainCount ? Math.round((correctRefusals / abstainCount) * 100) : null,
      avgFaithfulness: faithScores.length ? Math.round((faithScores.reduce((a, b) => a + b, 0) / faithScores.length) * 100) : null,
      avgLatency: latencies.length ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length) : 0,
    })

    setRunning(false)
  }

  const exportCSV = () => {
    const header = 'query,expected,should_find,answer,status,label,latency_ms,tokens,grounding\n'
    const rows = results.map(r =>
      [r.query, r.expected, r.should_find, `"${(r.answer || '').slice(0, 200).replace(/"/g, '""')}"`, r.status, labels[r.index] || 'Unlabeled', r.latency, r.tokens, r.grounding].join(',')
    ).join('\n')
    const blob = new Blob([header + rows], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'fare-eval-results.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  const filteredResults = results.filter(r => {
    if (filter === 'in_doc') return r.should_find
    if (filter === 'not_in_doc') return !r.should_find
    return true
  })

  const statusIcon = (status) => {
    if (status === 'found' || status === 'correct_refusal') return <CheckCircle2 size={14} className="text-[var(--color-success)]" />
    if (status === 'missed' || status === 'wrong_answer') return <XCircle size={14} className="text-[var(--color-danger)]" />
    if (status === 'error') return <AlertTriangle size={14} className="text-[var(--color-warning)]" />
    return null
  }

  const formatMeasured = (m) => {
    if (m.measured == null) return null
    return `${(m.measured * 100).toFixed(1)}%`
  }

  const formatCI = (m) => {
    if (!m.ci_95) return null
    return [`${(m.ci_95[0] * 100).toFixed(1)}%`, `${(m.ci_95[1] * 100).toFixed(1)}%`]
  }

  const getStatus = (m) => {
    if (m.measured == null) return 'unmeasured'
    return m.meets_target ? 'pass' : 'fail'
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">

        {/* Run management */}
        <div className="flex items-center flex-wrap gap-3">
          {runs.length > 0 && (
            <select
              value={selectedRun || ''}
              onChange={(e) => { setSelectedRun(e.target.value); loadDashboard(e.target.value) }}
              className="text-[13px] bg-transparent text-[var(--color-text-primary)] border border-[var(--color-border)] rounded-[var(--radius-input)] px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
            >
              {runs.map(r => (
                <option key={r.run_id} value={r.run_id}>
                  Run {r.run_id} — {r.status} ({r.completed_questions || 0}/{r.total_questions || '?'})
                </option>
              ))}
            </select>
          )}

          <button
            onClick={startNewRun}
            disabled={startingRun}
            className="flex items-center gap-2 px-4 py-2 text-[14px] font-medium bg-[var(--color-accent)] text-[var(--color-text-inverse)] rounded-[var(--radius-btn)] hover:bg-[var(--color-accent-hover)] transition-theme disabled:opacity-50"
          >
            {startingRun ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
            {startingRun ? 'Running...' : 'New eval run'}
          </button>

          <button
            onClick={fetchRuns}
            className="flex items-center gap-2 px-3 py-2 text-[14px] border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-primary)] rounded-[var(--radius-btn)] hover:bg-[var(--color-surface-tertiary)] transition-theme"
            title="Refresh runs"
          >
            <RefreshCw size={14} />
          </button>

          {selectedRun && (
            <>
              <button
                onClick={() => exportFromServer('csv')}
                className="flex items-center gap-2 px-3 py-2 text-[14px] border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-primary)] rounded-[var(--radius-btn)] hover:bg-[var(--color-surface-tertiary)] transition-theme ml-auto"
              >
                <Download size={14} /> CSV
              </button>
              <button
                onClick={() => exportFromServer('json')}
                className="flex items-center gap-2 px-3 py-2 text-[14px] border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-primary)] rounded-[var(--radius-btn)] hover:bg-[var(--color-surface-tertiary)] transition-theme"
              >
                <Download size={14} /> JSON
              </button>
              <button
                onClick={() => window.open(`${API}/api/eval/runs/${selectedRun}/report`, '_blank')}
                className="flex items-center gap-2 px-3 py-2 text-[14px] border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-primary)] rounded-[var(--radius-btn)] hover:bg-[var(--color-surface-tertiary)] transition-theme"
              >
                <FileText size={14} /> Report
              </button>
            </>
          )}
        </div>

        {/* Dashboard metric cards — all 10 + EM */}
        {dashboardMetrics && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
            {dashboardMetrics.metrics?.filter(m => m.key !== 'exact_match').map(m => (
              <MetricCard
                key={m.key}
                title={m.name}
                target={m.target_display || (m.target != null ? `>= ${(m.target * 100).toFixed(0)}%` : null)}
                measured={formatMeasured(m)}
                n={m.n || null}
                ci={formatCI(m)}
                formula={METRIC_FORMULAS[m.key]}
                icon={METRIC_ICONS[m.key] || CheckCircle2}
                status={getStatus(m)}
              />
            ))}
          </div>
        )}

        {/* Loading state for dashboard */}
        {loadingDashboard && (
          <div className="flex items-center justify-center py-8 gap-2 text-[var(--color-text-tertiary)]">
            <Loader2 size={16} className="animate-spin" /> Loading metrics...
          </div>
        )}

        {/* Confusion matrix */}
        {dashboardMetrics?.confusion && (
          <ConfusionMatrix confusion={dashboardMetrics.confusion} />
        )}

        {/* Legacy CSV-based quick run section */}
        <div className="border-t border-[var(--color-border)] pt-6">
          <p className="text-[13px] font-medium text-[var(--color-text-primary)] mb-3">Quick test (CSV upload)</p>
          <div className="flex items-center flex-wrap gap-3">
            <input ref={fileRef} type="file" accept=".csv" onChange={loadCSV} className="hidden" />
            <button
              onClick={() => fileRef.current?.click()}
              className="flex items-center gap-2 px-4 py-2 text-[14px] font-medium border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-primary)] rounded-[var(--radius-btn)] hover:bg-[var(--color-surface-tertiary)] transition-theme"
            >
              <Upload size={15} /> Load CSV
            </button>

            {testCases.length > 0 && !running && (
              <button
                onClick={runAll}
                className="flex items-center gap-2 px-4 py-2 text-[14px] font-medium bg-[var(--color-accent)] text-[var(--color-text-inverse)] rounded-[var(--radius-btn)] hover:bg-[var(--color-accent-hover)] transition-theme"
              >
                <Play size={15} /> Run all ({testCases.length})
              </button>
            )}

            {running && (
              <button
                onClick={() => { stopRef.current = true }}
                className="flex items-center gap-2 px-4 py-2 text-[14px] font-medium bg-[var(--color-danger)] text-[var(--color-text-inverse)] rounded-[var(--radius-btn)] hover:bg-red-700 transition-theme"
              >
                <Square size={14} fill="currentColor" /> Stop
              </button>
            )}

            {results.length > 0 && !running && (
              <button
                onClick={exportCSV}
                className="flex items-center gap-2 px-4 py-2 text-[14px] font-medium border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-primary)] rounded-[var(--radius-btn)] hover:bg-[var(--color-surface-tertiary)] transition-theme ml-auto"
              >
                <Download size={15} /> Export CSV
              </button>
            )}

            {testCases.length > 0 && (
              <span className="text-[12px] text-[var(--color-text-tertiary)]">
                {pluralize(testCases.length, 'test case')} loaded
              </span>
            )}
          </div>
        </div>

        {/* Progress bar */}
        {running && (
          <div>
            <div className="flex items-center justify-between text-[12px] text-[var(--color-text-tertiary)] mb-1">
              <span className="flex items-center gap-1"><Loader2 size={12} className="animate-spin" /> Running...</span>
              <span>{progress}% ({results.length}/{testCases.length})</span>
            </div>
            <div className="h-2 bg-[var(--color-surface-tertiary)] rounded-full overflow-hidden">
              <div className="h-full bg-[var(--color-accent)] rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}

        {/* Filter */}
        {results.length > 0 && (
          <div className="flex items-center gap-2">
            <Filter size={14} className="text-[var(--color-text-tertiary)]" />
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="text-[13px] bg-transparent text-[var(--color-text-primary)] border border-[var(--color-border)] rounded-[var(--radius-input)] px-2 py-1 focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
            >
              <option value="all">All ({results.length})</option>
              <option value="in_doc">Answer in document ({results.filter(r => r.should_find).length})</option>
              <option value="not_in_doc">Not in document ({results.filter(r => !r.should_find).length})</option>
            </select>
          </div>
        )}

        {/* Results table */}
        {filteredResults.length > 0 && (
          <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="bg-[var(--color-surface-tertiary)] text-[var(--color-text-tertiary)] text-left">
                    <th className="px-3 py-2 font-medium w-8">#</th>
                    <th className="px-3 py-2 font-medium">Query</th>
                    <th className="px-3 py-2 font-medium">Answer</th>
                    <th className="px-3 py-2 font-medium w-16 text-center">Status</th>
                    <th className="px-3 py-2 font-medium w-16 text-right">Time</th>
                    <th className="px-3 py-2 font-medium w-16 text-right">Tokens</th>
                    <th className="px-3 py-2 font-medium w-36">Label</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredResults.map((r) => {
                    const claims = claimsData[r.index]
                    const isExpanded = expandedClaims[r.index]
                    const unsupported = claims?.filter(c => !c.supported) || []
                    return (
                      <React.Fragment key={r.index}>
                        <tr className="border-t border-[var(--color-border)] hover:bg-[var(--color-surface-tertiary)]/50 transition-theme">
                          <td className="px-3 py-2 text-[var(--color-text-tertiary)] tabular-nums">{r.index + 1}</td>
                          <td className="px-3 py-2 text-[var(--color-text-primary)] max-w-[200px]">
                            <p className="truncate" title={r.query}>{r.query}</p>
                          </td>
                          <td className="px-3 py-2 text-[var(--color-text-secondary)] max-w-[250px]">
                            <div className="flex items-start gap-1">
                              <p className="truncate flex-1" title={r.answer}>{r.answer?.slice(0, 100) || '—'}</p>
                              {claims && (
                                <button onClick={() => toggleClaims(r.index)} className="shrink-0 p-0.5 rounded hover:bg-[var(--color-surface-tertiary)]" title={`${claims.length} claims, ${unsupported.length} unsupported`}>
                                  {unsupported.length > 0
                                    ? <ShieldAlert size={14} className="text-[var(--color-warning)]" />
                                    : <ShieldCheck size={14} className="text-[var(--color-success)]" />}
                                </button>
                              )}
                            </div>
                          </td>
                          <td className="px-3 py-2 text-center">{statusIcon(r.status)}</td>
                          <td className="px-3 py-2 text-right text-[var(--color-text-tertiary)] tabular-nums">{(r.latency / 1000).toFixed(1)}s</td>
                          <td className="px-3 py-2 text-right text-[var(--color-text-tertiary)] tabular-nums">{r.tokens.toLocaleString()}</td>
                          <td className="px-3 py-2">
                            <select
                              value={labels[r.index] || 'Unlabeled'}
                              onChange={(e) => setLabels(prev => ({ ...prev, [r.index]: e.target.value }))}
                              className={`w-full text-[12px] bg-transparent border border-[var(--color-border)] rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)] ${LABEL_COLORS[labels[r.index]] || 'text-[var(--color-text-tertiary)]'}`}
                            >
                              {LABELS.map(l => <option key={l} value={l}>{l}</option>)}
                            </select>
                          </td>
                        </tr>
                        {isExpanded && claims && (
                          <tr className="border-t border-[var(--color-border)]/50">
                            <td colSpan={7} className="px-3 py-2 bg-[var(--color-surface-secondary)]">
                              <div className="space-y-1.5">
                                <p className="text-[11px] font-medium text-[var(--color-text-tertiary)] uppercase tracking-wide">Claims ({claims.filter(c => c.supported).length}/{claims.length} supported)</p>
                                {claims.map((claim, ci) => (
                                  <div key={ci} className={`flex items-start gap-2 text-[12px] px-2 py-1.5 rounded ${claim.supported ? 'bg-[var(--color-success-subtle)]' : 'bg-[var(--color-danger-subtle)]'}`}>
                                    {claim.supported
                                      ? <ShieldCheck size={13} className="text-[var(--color-success)] shrink-0 mt-0.5" />
                                      : <ShieldAlert size={13} className="text-[var(--color-warning)] shrink-0 mt-0.5" />}
                                    <div className="flex-1 min-w-0">
                                      <p className="text-[var(--color-text-primary)]">{claim.text}</p>
                                      {claim.reason && <p className="text-[var(--color-text-tertiary)] text-[11px] mt-0.5">{claim.reason}</p>}
                                      {claim.supporting_chunk_id && <p className="text-[var(--color-text-tertiary)] text-[11px]">Chunk: {claim.supporting_chunk_id}</p>}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Empty state — only when no runs AND no CSV loaded */}
        {runs.length === 0 && testCases.length === 0 && !loadingDashboard && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-12 h-12 rounded-[var(--radius-card)] bg-[var(--color-surface-tertiary)] flex items-center justify-center mb-4">
              <BarChart3 size={24} className="text-[var(--color-text-tertiary)]" />
            </div>
            <p className="text-[16px] font-medium text-[var(--color-text-primary)]">No evaluation runs yet</p>
            <p className="text-[14px] text-[var(--color-text-secondary)] mt-1 max-w-sm">
              Click "New eval run" to run the labeled dataset, or upload a CSV for a quick test.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export default EvaluateTab
