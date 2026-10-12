import { useState } from 'react'

function DocumentList({ documents, onClear }) {
  const [confirming, setConfirming] = useState(false)

  const totalChunks = documents.reduce((sum, d) => sum + d.chunks_count, 0)

  return (
    <section className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-gray-900">
          Documents ({documents.length})
        </h2>
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

      <div className="space-y-2">
        {documents.map((doc) => (
          <div
            key={doc.doc_id}
            className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg"
          >
            <div className="flex items-center gap-2">
              <svg className="h-4 w-4 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                <path d="M4 18h12a2 2 0 002-2V6l-4-4H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span className="text-sm font-medium text-gray-700">{doc.doc_id}</span>
            </div>
            <span className="text-xs text-gray-500">{doc.chunks_count} chunks</span>
          </div>
        ))}
      </div>

      <p className="text-xs text-gray-400 mt-3">
        {totalChunks} total chunks across {documents.length} document{documents.length !== 1 ? 's' : ''}
      </p>
    </section>
  )
}

export default DocumentList
