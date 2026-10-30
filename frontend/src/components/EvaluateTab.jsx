import { useState, useRef } from 'react'
import { Play, Square, Upload, Download, Loader2, CheckCircle2, XCircle, AlertTriangle, Clock, Filter } from 'lucide-react'
import { pluralize } from '../utils/pluralize'

const API = 'http://localhost:8000'

const LABELS = ['Unlabeled', 'Correct', 'Faithful but wrong', 'Hallucinated', 'Correct refusal', 'Wrong refusal']
const LABEL_COLORS = {
  'Correct': 'text-[var(--color-success)]',
  'Faithful but wrong': 'text-[var(--color-warning)]',
  'Hallucinated': 'text-[var(--color-danger)]',
  'Correct refusal': 'text-[var(--color-success)]',
  'Wrong refusal': 'text-[var(--color-danger)]',
}

function MetricCard({ title, target, measured, icon: Icon }) {
  return (
    <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={16} className="text-[var(--color-text-tertiary)]" />
        <span className="text-[13px] font-medium text-[var(--color-text-primary)]">{title}</span>
      </div>
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-[12px] text-[var(--color-text-tertiary)]">Target</span>
          <span className="text-[14px] font-medium text-[var(--color-text-primary)]">{target}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[12px] text-[var(--color-text-tertiary)]">Measured</span>
          <span className={`text-[14px] font-medium ${measured === 'Not measured yet' ? 'text-[var(--color-text-tertiary)] italic' : 'text-[var(--color-text-primary)]'}`}>
            {measured}
          </span>
        </div>
      </div>
    </div>
  )
}

function EvaluateTab() {
  const [testCases, setTestCases] = useState([])
  const [results, setResults] = useState([])
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState(0)
  const [filter, setFilter] = useState('all')
  const [labels, setLabels] = useState({})
  const [summary, setSummary] = useState(null)
  const stopRef = useRef(false)
  const fileRef = useRef(null)

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
          index: i,
          query: tc.query,
          expected: tc.expected,
          should_find: tc.should_find,
          answer: data.answer || '',
          status,
          latency,
          tokens,
          chunks: data.sources?.length || 0,
          grounding: data.grounding?.score || 0,
        })
      } catch (err) {
        newResults.push({
          index: i,
          query: tc.query,
          expected: tc.expected,
          should_find: tc.should_find,
          answer: '',
          status: 'error',
          error: err.message,
          latency: Date.now() - start,
          tokens: 0,
          chunks: 0,
          grounding: 0,
        })
      }

      setResults([...newResults])
      setProgress(Math.round(((i + 1) / testCases.length) * 100))
    }

    const passCount = newResults.filter(r => r.status === 'found' || r.status === 'correct_refusal').length
    const latencies = newResults.filter(r => r.latency).map(r => r.latency)
    const faithScores = newResults.filter(r => r.should_find && r.status === 'found').map(r => r.grounding)
    const shouldFindCount = newResults.filter(r => r.should_find).length
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

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* Controls */}
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

        {/* Metric cards */}
        {(summary || results.length > 0) && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <MetricCard
              title="Abstention Rate"
              target=">=90%"
              measured={summary?.abstentionRate != null ? `${summary.abstentionRate}%` : 'Not measured yet'}
              icon={AlertTriangle}
            />
            <MetricCard
              title="Faithfulness"
              target=">=85%"
              measured={summary?.avgFaithfulness != null ? `${summary.avgFaithfulness}%` : 'Not measured yet'}
              icon={CheckCircle2}
            />
            <MetricCard
              title="Pass Rate"
              target="100%"
              measured={summary?.passRate != null ? `${summary.passRate}%` : 'Not measured yet'}
              icon={CheckCircle2}
            />
            <MetricCard
              title="Avg Latency"
              target="<5s"
              measured={summary?.avgLatency ? `${(summary.avgLatency / 1000).toFixed(1)}s` : 'Not measured yet'}
              icon={Clock}
            />
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
                  {filteredResults.map((r) => (
                    <tr key={r.index} className="border-t border-[var(--color-border)] hover:bg-[var(--color-surface-tertiary)]/50 transition-theme">
                      <td className="px-3 py-2 text-[var(--color-text-tertiary)] tabular-nums">{r.index + 1}</td>
                      <td className="px-3 py-2 text-[var(--color-text-primary)] max-w-[200px]">
                        <p className="truncate" title={r.query}>{r.query}</p>
                      </td>
                      <td className="px-3 py-2 text-[var(--color-text-secondary)] max-w-[250px]">
                        <p className="truncate" title={r.answer}>{r.answer?.slice(0, 100) || '—'}</p>
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
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Empty state */}
        {testCases.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-12 h-12 rounded-[var(--radius-card)] bg-[var(--color-surface-tertiary)] flex items-center justify-center mb-4">
              <Upload size={24} className="text-[var(--color-text-tertiary)]" />
            </div>
            <p className="text-[16px] font-medium text-[var(--color-text-primary)]">Load a test set to begin</p>
            <p className="text-[14px] text-[var(--color-text-secondary)] mt-1 max-w-sm">
              Upload a CSV with columns: query, expected (optional), should_find (true/false).
            </p>
            <p className="text-[12px] text-[var(--color-text-tertiary)] mt-3">
              Or use the built-in quick eval via the API: POST /api/eval/quick
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export default EvaluateTab
