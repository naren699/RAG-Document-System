import { useEffect, useRef, useState } from 'react'
import { X, Loader2, FileText, Hash } from 'lucide-react'

const API = 'http://localhost:8000'

function ChunkDrawer({ docId, onClose }) {
  const overlayRef = useRef(null)
  const [chunks, setChunks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!docId) return
    setLoading(true)
    setError(null)
    fetch(`${API}/api/documents/${encodeURIComponent(docId)}/chunks`)
      .then(r => r.json())
      .then(data => setChunks(data.chunks || []))
      .catch(() => setError('Failed to load chunks'))
      .finally(() => setLoading(false))
  }, [docId])

  useEffect(() => {
    const handleKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  if (!docId) return null

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50"
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <div className="absolute inset-0 bg-black/40" />
      <aside className="absolute inset-y-0 right-0 w-full max-w-md bg-[var(--color-surface)] shadow-lg flex flex-col transition-theme">
        {/* Header */}
        <div className="flex items-center justify-between h-14 px-4 border-b border-[var(--color-border)] shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <FileText size={16} className="text-[var(--color-text-tertiary)] shrink-0" />
            <span className="text-[14px] font-semibold text-[var(--color-text-primary)] truncate">{docId}</span>
            {!loading && (
              <span className="text-[12px] text-[var(--color-text-tertiary)] shrink-0">
                {chunks.length} chunk{chunks.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-[var(--radius-btn)] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-tertiary)]"
            aria-label="Close chunk viewer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto sidebar-scroll p-4 space-y-3">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={20} className="animate-spin text-[var(--color-text-tertiary)]" />
            </div>
          )}

          {error && (
            <p className="text-[14px] text-[var(--color-danger)] text-center py-8">{error}</p>
          )}

          {!loading && !error && chunks.length === 0 && (
            <p className="text-[14px] text-[var(--color-text-tertiary)] text-center py-8">No chunks found.</p>
          )}

          {!loading && !error && chunks.map((chunk, i) => (
            <div
              key={chunk.chunk_id}
              className="rounded-[var(--radius-btn)] border border-[var(--color-border)] bg-[var(--color-surface-secondary)] p-3 space-y-2"
            >
              {/* Chunk header */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="inline-flex items-center justify-center w-5 h-5 text-[11px] font-bold text-[var(--color-text-inverse)] bg-[var(--color-text-tertiary)] rounded">
                  {i + 1}
                </span>
                <span className="text-[12px] text-[var(--color-accent)] font-medium">
                  Page {chunk.page_num}
                </span>
                {chunk.section_title && (
                  <span className="text-[12px] text-[var(--color-text-secondary)] bg-[var(--color-surface-tertiary)] px-1.5 py-0.5 rounded">
                    {chunk.section_title}
                  </span>
                )}
                <span className="text-[12px] text-[var(--color-text-tertiary)] ml-auto flex items-center gap-1">
                  <Hash size={10} />
                  {chunk.token_count} tokens
                </span>
              </div>

              {/* Chunk text */}
              <p className="text-[13px] text-[var(--color-text-secondary)] leading-relaxed whitespace-pre-wrap">
                {chunk.text}
              </p>
            </div>
          ))}
        </div>
      </aside>
    </div>
  )
}

export default ChunkDrawer
