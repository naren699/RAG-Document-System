import { useState } from 'react'
import { pluralize } from '../utils/pluralize'

const API = 'http://localhost:8000'

function DocumentList({ documents, onClear, onDelete, onRechunk, selectedDocId, onSelectDoc }) {
  const [confirming, setConfirming] = useState(false)
  const [deletingId, setDeletingId] = useState(null)
  const [viewingDoc, setViewingDoc] = useState(null)
  const [chunks, setChunks] = useState([])
  const [loadingChunks, setLoadingChunks] = useState(false)
  const [rechunkingDoc, setRechunkingDoc] = useState(null)
  const [rechunkSize, setRechunkSize] = useState(300)
  const [rechunkOverlap, setRechunkOverlap] = useState(50)
  const [rechunking, setRechunking] = useState(false)

  const totalChunks = documents.reduce((sum, d) => sum + d.chunks_count, 0)

  const handleViewChunks = async (docId) => {
    if (viewingDoc === docId) {
      setViewingDoc(null)
      return
    }
    setViewingDoc(docId)
    setLoadingChunks(true)
    try {
      const res = await fetch(`${API}/api/documents/${encodeURIComponent(docId)}/chunks`)
      const data = await res.json()
      setChunks(data.chunks || [])
    } catch {
      setChunks([])
    } finally {
      setLoadingChunks(false)
    }
  }

  const handleRechunk = async (docId) => {
    setRechunking(true)
    try {
      await onRechunk(docId, rechunkSize, rechunkOverlap)
      setRechunkingDoc(null)
      if (viewingDoc === docId) handleViewChunks(docId)
    } finally {
      setRechunking(false)
    }
  }

  const handleDelete = async (docId) => {
    if (deletingId === docId) {
      await onDelete(docId)
      setDeletingId(null)
      if (viewingDoc === docId) setViewingDoc(null)
    } else {
      setDeletingId(docId)
    }
  }

  return (
    <section className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-gray-900">
          Documents ({documents.length})
        </h2>
        <div className="flex items-center gap-3">
          {selectedDocId && (
            <button
              onClick={() => onSelectDoc(null)}
              className="text-xs text-blue-600 hover:text-blue-800"
            >
              Clear filter
            </button>
          )}
          {!confirming ? (
            <button
              onClick={() => setConfirming(true)}
              className="text-sm text-red-500 hover:text-red-700 transition-colors"
            >
              Clear All
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">Delete all documents?</span>
              <button
                onClick={() => { onClear(); setConfirming(false) }}
                className="text-sm bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600 transition-colors"
              >
                Yes, delete
              </button>
              <button
                onClick={() => setConfirming(false)}
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="space-y-2">
        {documents.map((doc) => (
          <div key={doc.doc_id}>
            <div
              className={`flex items-center justify-between py-2 px-3 rounded-lg cursor-pointer transition-colors ${
                selectedDocId === doc.doc_id
                  ? 'bg-blue-50 border border-blue-200'
                  : 'bg-gray-50 hover:bg-gray-100'
              }`}
              onClick={() => onSelectDoc(selectedDocId === doc.doc_id ? null : doc.doc_id)}
            >
              <div className="flex items-center gap-2">
                <input
                  type="radio"
                  checked={selectedDocId === doc.doc_id}
                  onChange={() => onSelectDoc(selectedDocId === doc.doc_id ? null : doc.doc_id)}
                  onClick={(e) => e.stopPropagation()}
                  className="accent-blue-600"
                />
                <svg className="h-4 w-4 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M4 18h12a2 2 0 002-2V6l-4-4H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <span className="text-sm font-medium text-gray-700">{doc.doc_id}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">{pluralize(doc.chunks_count, 'chunk')}</span>
                <button
                  onClick={(e) => { e.stopPropagation(); handleViewChunks(doc.doc_id) }}
                  className="text-xs text-blue-500 hover:text-blue-700 transition-colors"
                  title="View chunks"
                >
                  {viewingDoc === doc.doc_id ? 'Hide' : 'View'}
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); setRechunkingDoc(rechunkingDoc === doc.doc_id ? null : doc.doc_id) }}
                  className="text-xs text-purple-500 hover:text-purple-700 transition-colors"
                  title="Re-chunk with different settings"
                >
                  Re-chunk
                </button>
                {deletingId === doc.doc_id ? (
                  <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => handleDelete(doc.doc_id)}
                      className="text-xs bg-red-500 text-white px-2 py-0.5 rounded hover:bg-red-600"
                    >
                      Confirm
                    </button>
                    <button
                      onClick={() => setDeletingId(null)}
                      className="text-xs text-gray-400 hover:text-gray-600"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(doc.doc_id) }}
                    className="text-xs text-red-400 hover:text-red-600 transition-colors"
                    title="Delete document"
                  >
                    Delete
                  </button>
                )}
              </div>
            </div>

            {rechunkingDoc === doc.doc_id && (
              <div className="mt-1 ml-6 border-l-2 border-purple-200 pl-3 py-2 bg-purple-50/30 rounded" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center gap-3 text-xs">
                  <label className="text-gray-600">
                    Chunk size:
                    <input type="number" min="50" max="1000" value={rechunkSize}
                      onChange={(e) => setRechunkSize(parseInt(e.target.value) || 300)}
                      className="ml-1 w-16 border border-gray-300 rounded px-1 py-0.5"
                    />
                  </label>
                  <label className="text-gray-600">
                    Overlap:
                    <input type="number" min="0" max="200" value={rechunkOverlap}
                      onChange={(e) => setRechunkOverlap(parseInt(e.target.value) || 0)}
                      className="ml-1 w-16 border border-gray-300 rounded px-1 py-0.5"
                    />
                  </label>
                  <button
                    onClick={() => handleRechunk(doc.doc_id)}
                    disabled={rechunking}
                    className="bg-purple-600 text-white px-2 py-0.5 rounded hover:bg-purple-700 disabled:bg-purple-300"
                  >
                    {rechunking ? 'Re-indexing...' : 'Re-index'}
                  </button>
                  <button onClick={() => setRechunkingDoc(null)} className="text-gray-400 hover:text-gray-600">Cancel</button>
                </div>
              </div>
            )}

            {viewingDoc === doc.doc_id && (
              <div className="mt-1 ml-6 border-l-2 border-gray-200 pl-3 space-y-1 max-h-60 overflow-y-auto">
                {loadingChunks ? (
                  <p className="text-xs text-gray-400 py-2">Loading chunks...</p>
                ) : chunks.length === 0 ? (
                  <p className="text-xs text-gray-400 py-2">No chunks found.</p>
                ) : (
                  chunks.map((chunk) => (
                    <div key={chunk.chunk_id} className="text-xs p-2 bg-gray-50 rounded">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-gray-600">{chunk.chunk_id}</span>
                        <span className="text-gray-400">Page {chunk.page_num}</span>
                        {chunk.section_title && (
                          <span className="text-purple-600 bg-purple-50 px-1 rounded">{chunk.section_title}</span>
                        )}
                        <span className="text-gray-400">{chunk.token_count} tokens</span>
                      </div>
                      <p className="text-gray-500 line-clamp-2">{chunk.text}</p>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between mt-3">
        <p className="text-xs text-gray-400">
          {pluralize(totalChunks, 'chunk')} across {pluralize(documents.length, 'document')}
        </p>
        {selectedDocId && (
          <p className="text-xs text-blue-600">
            Filtering queries to: {selectedDocId}
          </p>
        )}
      </div>
    </section>
  )
}

export default DocumentList
