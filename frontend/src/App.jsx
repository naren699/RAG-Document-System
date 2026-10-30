import { useState, useEffect, useCallback, useRef } from 'react'
import { PanelLeft } from 'lucide-react'
import { pluralize } from './utils/pluralize'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import QuestionBar from './components/QuestionBar'
import UploadSection from './components/UploadSection'
import ResultsSection from './components/ResultsSection'
import DocumentList from './components/DocumentList'
import SettingsPanel from './components/SettingsPanel'
import EvaluateTab from './components/EvaluateTab'
import Toast from './components/Toast'

const API = 'http://localhost:8000'

function useTheme() {
  const [theme, setTheme] = useState(() => localStorage.getItem('fare-theme') || 'system')

  useEffect(() => {
    const root = document.documentElement
    root.classList.remove('light', 'dark')
    if (theme !== 'system') root.classList.add(theme)
    localStorage.setItem('fare-theme', theme)
  }, [theme])

  const toggle = () => setTheme(prev => prev === 'system' ? 'light' : prev === 'light' ? 'dark' : 'system')

  return { theme, toggle }
}

function App() {
  const { theme, toggle: toggleTheme } = useTheme()
  const [activeTab, setActiveTab] = useState('ask')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const [documents, setDocuments] = useState([])
  const [uploadStatus, setUploadStatus] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(null)
  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [searchHistory, setSearchHistory] = useState([])
  const [selectedDocId, setSelectedDocId] = useState(null)
  const [conversationHistory, setConversationHistory] = useState([])
  const [pastResults, setPastResults] = useState([])
  const [toast, setToast] = useState(null)

  const [settings, setSettings] = useState({
    topK: 5,
    method: 'hybrid',
    scoreThreshold: -2.0,
    maskPii: false,
  })

  const abortRef = useRef(null)
  const conversationEndRef = useRef(null)

  const fetchDocuments = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/documents`)
      const data = await res.json()
      setDocuments(data.documents || [])
    } catch {
      setDocuments([])
    }
  }, [])

  useEffect(() => { fetchDocuments() }, [fetchDocuments])

  const handleUpload = async (file, excludePages) => {
    setIsUploading(true)
    setUploadStatus(null)
    setUploadProgress(0)
    setError(null)

    const formData = new FormData()
    formData.append('file', file)
    if (excludePages) formData.append('exclude_pages', excludePages)

    try {
      const data = await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        xhr.open('POST', `${API}/api/ingest`)
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) setUploadProgress(Math.round((e.loaded / e.total) * 100))
        }
        xhr.onload = () => {
          try {
            const json = JSON.parse(xhr.responseText)
            if (xhr.status >= 200 && xhr.status < 300) resolve(json)
            else reject(new Error(json.detail || 'Upload failed'))
          } catch { reject(new Error('Invalid response from server')) }
        }
        xhr.onerror = () => reject(new Error('Cannot reach backend. Is the server running?'))
        xhr.send(formData)
      })

      const msg = `${pluralize(data.chunks_count, 'chunk')} created from ${pluralize(data.total_pages, 'page')}`
      setUploadStatus({ success: true, message: msg, warnings: data.warnings || [], data })
      setToast({ message: msg, type: 'success' })
      setTimeout(() => setUploadStatus(null), 4000)
      fetchDocuments()
    } catch (err) {
      setUploadStatus({ success: false, message: err.message })
    } finally {
      setIsUploading(false)
      setUploadProgress(null)
    }
  }

  const handleClear = async () => {
    try {
      await fetch(`${API}/api/clear`, { method: 'DELETE' })
      setDocuments([])
      setResult(null)
      setUploadStatus(null)
      setSelectedDocId(null)
    } catch { setError('Failed to clear documents') }
  }

  const handleDeleteDoc = async (docId) => {
    try {
      const res = await fetch(`${API}/api/documents/${encodeURIComponent(docId)}`, { method: 'DELETE' })
      if (!res.ok) {
        const data = await res.json()
        setError(data.detail || 'Failed to delete document')
        return
      }
      if (selectedDocId === docId) setSelectedDocId(null)
      fetchDocuments()
    } catch { setError('Failed to delete document') }
  }

  const handleRechunk = async (docId, chunkSize, chunkOverlap) => {
    try {
      const res = await fetch(`${API}/api/documents/${encodeURIComponent(docId)}/rechunk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chunk_size: chunkSize, chunk_overlap: chunkOverlap }),
      })
      if (!res.ok) {
        const data = await res.json()
        setError(data.detail || 'Re-chunk failed')
        return
      }
      fetchDocuments()
    } catch { setError('Failed to re-chunk document') }
  }

  const handleStop = () => {
    if (abortRef.current) { abortRef.current.abort(); abortRef.current = null }
    setIsSearching(false)
    setIsStreaming(false)
  }

  const handleSearch = async (overrideQuery) => {
    const q = overrideQuery || query
    if (!q.trim()) return
    if (overrideQuery) setQuery(overrideQuery)
    if (result && !result.is_not_found) {
      setPastResults(prev => [...prev, { query: q, result }].slice(-20))
    }
    setIsSearching(true)
    setIsStreaming(true)
    setResult(null)
    setError(null)

    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const timeoutId = setTimeout(() => controller.abort(), 120_000)

    try {
      const res = await fetch(`${API}/api/query/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: q,
          k: settings.topK,
          method: settings.method,
          doc_id: selectedDocId,
          score_threshold: settings.scoreThreshold,
          history: conversationHistory.slice(-6),
          mask_pii: settings.maskPii,
        }),
        signal: controller.signal,
      })

      if (!res.ok) {
        const data = await res.json()
        setError(data.detail || 'Query failed')
        setIsSearching(false)
        setIsStreaming(false)
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let answerSoFar = ''
      let sources = []
      let finalResult = null
      let rewrittenQuery = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let eventType = null
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim()
          } else if (line.startsWith('data: ') && eventType) {
            const data = JSON.parse(line.slice(6))
            if (eventType === 'rewritten_query') {
              rewrittenQuery = data
              setResult(prev => ({ ...(prev || {}), rewritten_query: data }))
            } else if (eventType === 'sources') {
              sources = data
              setResult(prev => ({ ...(prev || {}), sources: data, answer: '', is_not_found: false }))
            } else if (eventType === 'token') {
              answerSoFar += data
              setResult(prev => ({ ...(prev || {}), answer: answerSoFar }))
            } else if (eventType === 'done') {
              finalResult = data
            } else if (eventType === 'error') {
              setError(data.error || 'Streaming error')
            }
            eventType = null
          }
        }
      }

      setIsStreaming(false)
      if (finalResult) {
        const answerText = finalResult.answer || answerSoFar
        setResult({
          answer: answerText,
          sources,
          is_not_found: finalResult.is_not_found || false,
          provider: finalResult.provider,
          model: finalResult.model,
          tokens_used: finalResult.tokens_used,
          grounding: finalResult.grounding,
          timings: finalResult.timings,
          estimated_cost_usd: finalResult.estimated_cost_usd,
          rewritten_query: rewrittenQuery,
        })
        if (!finalResult.is_not_found) {
          setConversationHistory(prev => [
            ...prev,
            { role: 'user', content: q },
            { role: 'assistant', content: answerText },
          ].slice(-10))
        }
      }

      setSearchHistory(prev => {
        const filtered = prev.filter(h => h !== q.trim())
        return [q.trim(), ...filtered].slice(0, 10)
      })
    } catch (err) {
      setIsStreaming(false)
      if (err.name === 'AbortError') {
        setError('Query timed out. The LLM may be overloaded — try again.')
      } else {
        setError('Cannot reach backend. Is the server running?')
      }
    } finally {
      clearTimeout(timeoutId)
      setIsSearching(false)
      abortRef.current = null
    }
  }

  const handleFeedback = async (rating, reason) => {
    if (!result) return
    try {
      await fetch(`${API}/api/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          answer: result.answer,
          rating,
          reason: reason || null,
          sources: result.sources?.map(s => s.chunk_id) || [],
        }),
      })
    } catch { /* silently ignore */ }
  }

  const [providerInfo, setProviderInfo] = useState(null)
  useEffect(() => {
    fetch(`${API}/api/debug`).then(r => r.json()).then(d => setProviderInfo(d)).catch(() => {})
  }, [])

  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [result, pastResults.length])

  const hasDocuments = documents.length > 0

  const sidebarContent = (
    <>
      <UploadSection
        onUpload={handleUpload}
        isUploading={isUploading}
        uploadStatus={uploadStatus}
        uploadProgress={uploadProgress}
        llmProvider={providerInfo?.llm_provider}
        compact={hasDocuments}
      />

      {hasDocuments && (
        <DocumentList
          documents={documents}
          onClear={handleClear}
          onDelete={handleDeleteDoc}
          onRechunk={handleRechunk}
          selectedDocId={selectedDocId}
          onSelectDoc={setSelectedDocId}
        />
      )}

      <SettingsPanel settings={settings} onChange={setSettings} />
    </>
  )

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-[var(--color-surface-secondary)] transition-theme">
      <Header
        providerInfo={providerInfo}
        theme={theme}
        onToggleTheme={toggleTheme}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      {activeTab === 'ask' ? (
        <div className="flex flex-1 overflow-hidden">
          <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)}>
            {sidebarContent}
          </Sidebar>

          <main className="flex-1 flex flex-col overflow-hidden">
            {/* Mobile documents button */}
            <div className="lg:hidden flex items-center gap-2 px-4 py-2 border-b border-[var(--color-border)] bg-[var(--color-surface)] transition-theme">
              <button
                onClick={() => setSidebarOpen(true)}
                className="flex items-center gap-2 px-3 py-1.5 text-[14px] font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] bg-[var(--color-surface-tertiary)] rounded-[var(--radius-btn)] transition-theme"
                aria-label="Open documents sidebar"
              >
                <PanelLeft size={16} />
                Documents
                {hasDocuments && (
                  <span className="text-[12px] text-[var(--color-text-tertiary)]">({documents.length})</span>
                )}
              </button>
              {selectedDocId && (
                <span className="text-[12px] text-[var(--color-accent)] truncate">
                  Filtering: {selectedDocId}
                </span>
              )}
            </div>

            {/* Conversation area */}
            <div className="flex-1 overflow-y-auto">
              <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
                {error && (
                  <div className="flex items-start gap-3 p-4 rounded-[var(--radius-card)] bg-[var(--color-danger-subtle)] border border-[var(--color-danger)]/20 text-[14px] text-[var(--color-danger)]">
                    <span className="flex-1">{error}</span>
                    <button
                      onClick={() => { setError(null); handleSearch() }}
                      className="text-[14px] font-medium hover:underline shrink-0"
                    >
                      Retry
                    </button>
                  </div>
                )}

                {/* Empty state: example questions */}
                {hasDocuments && !result && !isSearching && pastResults.length === 0 && !error && (
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <p className="text-[14px] text-[var(--color-text-tertiary)] mb-4">Try one of these questions</p>
                    <div className="flex flex-wrap justify-center gap-2">
                      {['Summarize this document', 'What are the key points?', 'What is this document about?'].map(eg => (
                        <button
                          key={eg}
                          onClick={() => handleSearch(eg)}
                          className="px-4 py-2 text-[14px] text-[var(--color-accent)] bg-[var(--color-accent-subtle)] rounded-full hover:bg-[var(--color-accent)]/15 transition-theme"
                        >
                          {eg}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* No documents empty state */}
                {!hasDocuments && !error && (
                  <div className="flex flex-col items-center justify-center py-24 text-center">
                    <div className="w-12 h-12 rounded-[var(--radius-card)] bg-[var(--color-surface-tertiary)] flex items-center justify-center mb-4">
                      <svg className="w-6 h-6 text-[var(--color-text-tertiary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                    </div>
                    <p className="text-[16px] font-medium text-[var(--color-text-primary)]">Upload a document to get started</p>
                    <p className="text-[14px] text-[var(--color-text-tertiary)] mt-1 max-w-xs">
                      Drop a PDF in the sidebar, then ask questions about it.
                    </p>
                  </div>
                )}

                {/* Past conversation turns */}
                {pastResults.map((past, i) => (
                  <div key={i} className="space-y-3">
                    <div className="flex items-start gap-3">
                      <div className="w-7 h-7 rounded-full bg-[var(--color-accent-subtle)] flex items-center justify-center shrink-0 mt-0.5">
                        <span className="text-[12px] font-semibold text-[var(--color-accent)]">Q</span>
                      </div>
                      <p className="text-[14px] font-medium text-[var(--color-text-primary)] pt-1">{past.query}</p>
                    </div>
                    <div className="ml-10 p-4 rounded-[var(--radius-card)] bg-[var(--color-surface)] border border-[var(--color-border)] transition-theme">
                      <p className="text-[14px] text-[var(--color-text-secondary)] line-clamp-4">{past.result.answer}</p>
                      {past.result.sources?.length > 0 && (
                        <p className="text-[12px] text-[var(--color-text-tertiary)] mt-2">
                          {pluralize(past.result.sources.length, 'source')}
                        </p>
                      )}
                    </div>
                  </div>
                ))}

                {pastResults.length > 0 && (result || isSearching) && (
                  <hr className="border-[var(--color-border)]" />
                )}

                {/* Current question */}
                {(result || isSearching) && (
                  <div className="flex items-start gap-3">
                    <div className="w-7 h-7 rounded-full bg-[var(--color-accent-subtle)] flex items-center justify-center shrink-0 mt-0.5">
                      <span className="text-[12px] font-semibold text-[var(--color-accent)]">Q</span>
                    </div>
                    <p className="text-[14px] font-medium text-[var(--color-text-primary)] pt-1">{query}</p>
                  </div>
                )}

                {/* Skeleton loading state */}
                {isSearching && !result && (
                  <div className="ml-10 p-6 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] shadow-[var(--shadow-card)] space-y-3 animate-pulse">
                    <div className="h-4 w-24 bg-[var(--color-surface-tertiary)] rounded" />
                    <div className="space-y-2">
                      <div className="h-4 w-full bg-[var(--color-surface-tertiary)] rounded" />
                      <div className="h-4 w-5/6 bg-[var(--color-surface-tertiary)] rounded" />
                      <div className="h-4 w-3/4 bg-[var(--color-surface-tertiary)] rounded" />
                    </div>
                  </div>
                )}

                {/* Current result (replaces skeleton once answer arrives) */}
                {result && (
                  <div className="ml-10">
                    <ResultsSection
                      result={result}
                      query={query}
                      isStreaming={isStreaming}
                      onFeedback={handleFeedback}
                    />
                  </div>
                )}

                <div ref={conversationEndRef} />
              </div>
            </div>

            {/* Fixed question bar */}
            <QuestionBar
              query={query}
              onQueryChange={setQuery}
              onSearch={handleSearch}
              onStop={handleStop}
              isSearching={isSearching}
              disabled={!hasDocuments}
              searchHistory={searchHistory}
              onSelectHistory={setQuery}
            />
          </main>
        </div>
      ) : (
        <EvaluateTab />
      )}

      <Toast
        message={toast?.message}
        type={toast?.type}
        onClose={() => setToast(null)}
      />
    </div>
  )
}

export default App
