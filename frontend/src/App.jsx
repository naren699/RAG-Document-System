import { useState, useEffect, useCallback } from 'react'
import Header from './components/Header'
import UploadSection from './components/UploadSection'
import QuerySection from './components/QuerySection'
import ResultsSection from './components/ResultsSection'
import DocumentList from './components/DocumentList'

const API = 'http://localhost:8000'

function App() {
  const [documents, setDocuments] = useState([])
  const [uploadStatus, setUploadStatus] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(null)
  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [searchHistory, setSearchHistory] = useState([])

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

  const handleUpload = async (file) => {
    setIsUploading(true)
    setUploadStatus(null)
    setUploadProgress(0)
    setError(null)

    const formData = new FormData()
    formData.append('file', file)

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

      setUploadStatus({
        success: true,
        message: `Uploaded! ${data.chunks_count} chunks created from ${data.total_pages} pages`,
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
    } catch {
      setError('Failed to clear documents')
    }
  }

  const handleSearch = async () => {
    if (!query.trim()) return
    setIsSearching(true)
    setResult(null)
    setError(null)

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 60_000)

    try {
      const res = await fetch(`${API}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, k: 5, method: 'hybrid' }),
        signal: controller.signal,
      })
      const data = await res.json()

      if (!res.ok) {
        setError(data.detail || 'Query failed')
        return
      }

      setResult(data)
      setSearchHistory(prev => {
        const filtered = prev.filter(q => q !== query.trim())
        return [query.trim(), ...filtered].slice(0, 10)
      })
    } catch (err) {
      if (err.name === 'AbortError') {
        setError('Query timed out after 60 seconds. The LLM may be overloaded — try again.')
      } else {
        setError('Cannot reach backend. Is the server running?')
      }
    } finally {
      clearTimeout(timeoutId)
      setIsSearching(false)
    }
  }

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
        />

        {hasDocuments && (
          <DocumentList documents={documents} onClear={handleClear} />
        )}

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
            {error}
          </div>
        )}

        {result && <ResultsSection result={result} query={query} />}
      </main>
    </div>
  )
}

export default App
