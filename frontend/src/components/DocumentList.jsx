import { useState, useRef, useEffect } from 'react'
import { pluralize } from '../utils/pluralize'
import { FileText, MoreHorizontal, Eye, Scissors, Trash2, Loader2, Filter } from 'lucide-react'
import Dialog from './Dialog'
import ChunkDrawer from './ChunkDrawer'

function ContextMenu({ open, onClose, position, items }) {
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const handleClick = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose() }
    const handleKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('mousedown', handleClick)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleClick)
      document.removeEventListener('keydown', handleKey)
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      ref={ref}
      className="absolute z-30 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-btn)] shadow-[var(--shadow-popover)] py-1 min-w-[140px]"
      style={{ top: position.top, right: position.right }}
    >
      {items.map((item, i) => (
        <button
          key={i}
          onClick={() => { item.onClick(); onClose() }}
          className={`w-full flex items-center gap-2 px-3 py-2 text-[13px] text-left transition-theme ${
            item.danger
              ? 'text-[var(--color-danger)] hover:bg-[var(--color-danger-subtle)]'
              : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-tertiary)] hover:text-[var(--color-text-primary)]'
          }`}
        >
          {item.icon}
          {item.label}
        </button>
      ))}
    </div>
  )
}

function RechunkPanel({ docId, onRechunk, onClose }) {
  const [size, setSize] = useState(300)
  const [overlap, setOverlap] = useState(50)
  const [loading, setLoading] = useState(false)

  const handleApply = async () => {
    setLoading(true)
    await onRechunk(docId, size, overlap)
    setLoading(false)
    onClose()
  }

  return (
    <div className="p-3 border border-[var(--color-border)] rounded-[var(--radius-btn)] bg-[var(--color-surface-secondary)] space-y-3">
      <p className="text-[12px] font-medium text-[var(--color-text-primary)]">Re-chunk: {docId}</p>
      <div className="flex items-center gap-3">
        <label className="text-[12px] text-[var(--color-text-secondary)] flex items-center gap-1">
          Size
          <input
            type="number" min="50" max="1000" value={size}
            onChange={(e) => setSize(parseInt(e.target.value) || 300)}
            className="w-16 border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-primary)] rounded-[var(--radius-input)] px-2 py-1 text-[12px] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
          />
        </label>
        <label className="text-[12px] text-[var(--color-text-secondary)] flex items-center gap-1">
          Overlap
          <input
            type="number" min="0" max="200" value={overlap}
            onChange={(e) => setOverlap(parseInt(e.target.value) || 0)}
            className="w-16 border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-primary)] rounded-[var(--radius-input)] px-2 py-1 text-[12px] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
          />
        </label>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={handleApply}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium bg-[var(--color-accent)] text-[var(--color-text-inverse)] rounded-[var(--radius-btn)] hover:bg-[var(--color-accent-hover)] disabled:opacity-50 transition-theme"
        >
          {loading && <Loader2 size={12} className="animate-spin" />}
          {loading ? 'Re-indexing...' : 'Re-index'}
        </button>
        <button
          onClick={onClose}
          className="px-3 py-1.5 text-[12px] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)] transition-theme"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

function DocumentList({ documents, onClear, onDelete, onRechunk, selectedDocId, onSelectDoc }) {
  const [menuDocId, setMenuDocId] = useState(null)
  const [menuPos, setMenuPos] = useState({ top: 0, right: 0 })
  const [deleteDialog, setDeleteDialog] = useState(null)
  const [clearDialog, setClearDialog] = useState(false)
  const [viewingDocId, setViewingDocId] = useState(null)
  const [rechunkDocId, setRechunkDocId] = useState(null)

  const totalChunks = documents.reduce((sum, d) => sum + d.chunks_count, 0)

  const openMenu = (docId, e) => {
    e.stopPropagation()
    const rect = e.currentTarget.getBoundingClientRect()
    const parentRect = e.currentTarget.closest('section').getBoundingClientRect()
    setMenuPos({ top: rect.bottom - parentRect.top + 4, right: 8 })
    setMenuDocId(menuDocId === docId ? null : docId)
  }

  const menuItems = (docId) => [
    { icon: <Eye size={14} />, label: 'View chunks', onClick: () => setViewingDocId(docId) },
    { icon: <Scissors size={14} />, label: 'Re-chunk', onClick: () => setRechunkDocId(docId) },
    { icon: <Trash2 size={14} />, label: 'Delete', danger: true, onClick: () => setDeleteDialog(docId) },
  ]

  return (
    <section className="relative space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-[14px] font-semibold text-[var(--color-text-primary)]">
          Documents
          <span className="text-[var(--color-text-tertiary)] font-normal ml-1">({documents.length})</span>
        </h3>
        {documents.length > 1 && (
          <button
            onClick={() => setClearDialog(true)}
            className="text-[12px] text-[var(--color-danger)] hover:underline"
          >
            Clear all
          </button>
        )}
      </div>

      {/* Filter control */}
      <div className="flex items-center gap-2 p-2 rounded-[var(--radius-btn)] bg-[var(--color-surface-tertiary)]">
        <Filter size={13} className="text-[var(--color-text-tertiary)] shrink-0" />
        <span className="text-[12px] text-[var(--color-text-tertiary)]">Search in:</span>
        <select
          value={selectedDocId || ''}
          onChange={(e) => onSelectDoc(e.target.value || null)}
          className="flex-1 text-[12px] bg-transparent text-[var(--color-text-primary)] border-none outline-none cursor-pointer"
        >
          <option value="">All documents</option>
          {documents.map(d => (
            <option key={d.doc_id} value={d.doc_id}>{d.doc_id}</option>
          ))}
        </select>
      </div>

      {/* Document rows */}
      <div className="space-y-1">
        {documents.map((doc) => (
          <div key={doc.doc_id}>
            <div
              className={`flex items-center gap-2 px-3 py-2 rounded-[var(--radius-btn)] cursor-pointer transition-theme ${
                selectedDocId === doc.doc_id
                  ? 'bg-[var(--color-accent-subtle)] border border-[var(--color-accent)]/30'
                  : 'hover:bg-[var(--color-surface-tertiary)]'
              }`}
              onClick={() => onSelectDoc(selectedDocId === doc.doc_id ? null : doc.doc_id)}
            >
              <FileText size={15} className="text-[var(--color-danger)] shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-medium text-[var(--color-text-primary)] truncate">{doc.doc_id}</p>
                <p className="text-[11px] text-[var(--color-text-tertiary)]">
                  {pluralize(doc.chunks_count, 'chunk')}
                </p>
              </div>
              <button
                onClick={(e) => openMenu(doc.doc_id, e)}
                className="p-1.5 rounded-[var(--radius-btn)] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-tertiary)] transition-theme"
                aria-label={`Actions for ${doc.doc_id}`}
              >
                <MoreHorizontal size={15} />
              </button>
            </div>

            {rechunkDocId === doc.doc_id && (
              <div className="mt-1 ml-6">
                <RechunkPanel docId={doc.doc_id} onRechunk={onRechunk} onClose={() => setRechunkDocId(null)} />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Summary */}
      <p className="text-[11px] text-[var(--color-text-tertiary)]">
        {pluralize(totalChunks, 'chunk')} across {pluralize(documents.length, 'document')}
      </p>

      {/* Context menu */}
      <ContextMenu
        open={menuDocId !== null}
        onClose={() => setMenuDocId(null)}
        position={menuPos}
        items={menuDocId ? menuItems(menuDocId) : []}
      />

      {/* Delete confirmation */}
      <Dialog
        open={deleteDialog !== null}
        onClose={() => setDeleteDialog(null)}
        title="Delete document"
        description={`This will permanently delete "${deleteDialog}" and all its chunks. This cannot be undone.`}
        danger
        confirmLabel="Delete"
        onConfirm={() => { onDelete(deleteDialog); setDeleteDialog(null) }}
      />

      {/* Clear all confirmation */}
      <Dialog
        open={clearDialog}
        onClose={() => setClearDialog(false)}
        title="Clear all documents"
        description={`This will permanently delete all ${documents.length} document${documents.length !== 1 ? 's' : ''} and ${totalChunks} chunk${totalChunks !== 1 ? 's' : ''}. This cannot be undone.`}
        danger
        confirmLabel="Delete all"
        onConfirm={() => { onClear(); setClearDialog(false) }}
      />

      {/* Chunk drawer */}
      {viewingDocId && (
        <ChunkDrawer docId={viewingDocId} onClose={() => setViewingDocId(null)} />
      )}
    </section>
  )
}

export default DocumentList
