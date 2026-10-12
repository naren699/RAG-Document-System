import { useState, useEffect, useCallback } from 'react'
import Header from './components/Header'
import UploadSection from './components/UploadSection'
import QuerySection from './components/QuerySection'
import ResultsSection from './components/ResultsSection'
import DocumentList from './components/DocumentList'

const API = 'http://localhost:8005'

function App() {
  const [documents, setDocuments] = useState([])
  const [uploadStatus, setUploadStatus] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

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
    setError(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch(`${API}/api/ingest`, { method: 'POST', body: formData })
      const data = await res.json()

      if (!res.ok) {
        setUploadStatus({ success: false, message: data.detail || 'Upload failed' })
        return
      }

      setUploadStatus({
        success: true,
        message: `Uploaded! ${data.chunks_count} chunks created from ${data.total_pages} pages`,
        data,
      })
      fetchDocuments()
    } catch {
      setUploadStatus({ success: false, message: 'Cannot reach backend. Is the server running?' })
    } finally {
      setIsUploading(false)
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

    try {
      const res = await fetch(`${API}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, k: 5, method: 'hybrid' }),
      })
      const data = await res.json()

      if (!res.ok) {
        setError(data.detail || 'Query failed')
        return
      }

      setResult(data)
    } catch {
      setError('Cannot reach backend. Is the server running?')
    } finally {
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
        />

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            {error}
          </div>
        )}

        {result && <ResultsSection result={result} />}
      </main>
    </div>
  )
}

export default App
