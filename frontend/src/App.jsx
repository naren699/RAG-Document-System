import { useState, useEffect, useCallback, useRef } from 'react'
import { pluralize } from './utils/pluralize'
import Header from './components/Header'
import UploadSection from './components/UploadSection'
import QuerySection from './components/QuerySection'
import ResultsSection from './components/ResultsSection'
import DocumentList from './components/DocumentList'
import SettingsPanel from './components/SettingsPanel'

const API = 'http://localhost:8000'

function App() {
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

  const [settings, setSettings] = useState({
    topK: 5,
    method: 'hybrid',
    scoreThreshold: -2.0,
    maskPii: false,
  })

  const abortRef = useRef(null)

  const fetchDocuments = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/documents`)
      const data = await res.json()
      setDocuments(data.documents || [])
    } catch {
      setDocuments([])
    }
  }, [])

  useEffect(() => {
    fetchDocuments()
  }, [fetchDocuments])

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
          if (e.lengthComputable) {
            setUploadProgress(Math.round((e.loaded / e.total) * 100))
          }
        }

        xhr.onload = () => {
          try {
            const json = JSON.parse(xhr.responseText)
            if (xhr.status >= 200 && xhr.status < 300) {
              resolve(json)
            } else {
              reject(new Error(json.detail || 'Upload failed'))
            }
          } catch {
            reject(new Error('Invalid response from server'))
          }
        }

        xhr.onerror = () => reject(new Error('Cannot reach backend. Is the server running?'))
        xhr.send(formData)
      })

      let message = `Uploaded! ${pluralize(data.chunks_count, 'chunk')} created from ${pluralize(data.total_pages, 'page')}`
      if (data.excluded_pages?.length) {
        message += ` (excluded pages: ${data.excluded_pages.join(', ')})`
      }

      setUploadStatus({
        success: true,
        message,
        warnings: data.warnings || [],
        data,
      })
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
    } catch {
      setError('Failed to clear documents')
    }
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
    } catch {
      setError('Failed to delete document')
    }
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
    } catch {
      setError('Failed to re-chunk document')
    }
  }

  const handleSearch = async () => {
    if (!query.trim()) return
    if (result && !result.is_not_found) {
      setPastResults(prev => [...prev, { query, result }].slice(-5))
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
          query,
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
              setResult(prev => ({
                ...(prev || {}),
                rewritten_query: data,
              }))
            } else if (eventType === 'sources') {
              sources = data
              setResult(prev => ({
                ...(prev || {}),
                sources: data,
                answer: '',
                is_not_found: false,
              }))
            } else if (eventType === 'token') {
              answerSoFar += data
              setResult(prev => ({
                ...(prev || {}),
                answer: answerSoFar,
              }))
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
            { role: 'user', content: query },
            { role: 'assistant', content: answerText },
          ].slice(-10))
        }
      }

      setSearchHistory(prev => {
        const filtered = prev.filter(q => q !== query.trim())
        return [query.trim(), ...filtered].slice(0, 10)
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

  const handleFeedback = async (rating) => {
    if (!result) return
    try {
      await fetch(`${API}/api/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          answer: result.answer,
          rating,
        }),
      })
    } catch {
      // silently ignore feedback errors
    }
  }

  const [providerInfo, setProviderInfo] = useState(null)

  useEffect(() => {
    fetch(`${API}/api/debug`).then(r => r.json()).then(d => setProviderInfo(d)).catch(() => {})
  }, [])

  const hasDocuments = documents.length > 0

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-4xl mx-auto px-4 py-8 space-y-8">
        <UploadSection
          onUpload={handleUpload}
          isUploading={isUploading}
          uploadStatus={uploadStatus}
          uploadProgress={uploadProgress}
          llmProvider={providerInfo?.llm_provider}
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

        <QuerySection
          query={query}
          onQueryChange={setQuery}
          onSearch={handleSearch}
          isSearching={isSearching}
          disabled={!hasDocuments}
          searchHistory={searchHistory}
          onSelectHistory={setQuery}
        />

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            <div className="flex items-center justify-between">
              <span>{error}</span>
              <button
                onClick={() => { setError(null); handleSearch() }}
                className="text-sm text-red-600 hover:text-red-800 font-medium ml-3"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {pastResults.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-gray-500">Conversation History</h3>
              <button
                onClick={() => { setPastResults([]); setConversationHistory([]) }}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                Clear history
              </button>
            </div>
            {pastResults.map((past, i) => (
              <div key={i} className="bg-gray-50 rounded-lg border border-gray-100 p-4 opacity-70">
                <p className="text-sm font-medium text-gray-600 mb-1">Q: {past.query}</p>
                <p className="text-sm text-gray-500 line-clamp-3">{past.result.answer}</p>
              </div>
            ))}
          </div>
        )}

        {result && (
          <ResultsSection
            result={result}
            query={query}
            isStreaming={isStreaming}
            onFeedback={handleFeedback}
          />
        )}
      </main>
    </div>
  )
}

export default App
