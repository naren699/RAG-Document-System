import { useRef, useState } from 'react'
import { Upload, Loader2, Info, CheckCircle2, XCircle } from 'lucide-react'

const MAX_SIZE = 50 * 1024 * 1024

function UploadSection({ onUpload, isUploading, uploadStatus, uploadProgress, llmProvider, compact }) {
  const inputRef = useRef(null)
  const [dragOver, setDragOver] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [sizeError, setSizeError] = useState(null)
  const [excludePages, setExcludePages] = useState('')
  const [privacyDismissed, setPrivacyDismissed] = useState(() => localStorage.getItem('fare-privacy-dismissed') === '1')

  const dismissPrivacy = () => { setPrivacyDismissed(true); localStorage.setItem('fare-privacy-dismissed', '1') }

  const validateAndSelect = (file) => {
    setSizeError(null)
    if (file.size > MAX_SIZE) {
      setSizeError(`File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum is 50 MB.`)
      return
    }
    setSelectedFile(file)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file?.type === 'application/pdf') validateAndSelect(file)
  }

  const handleFileChange = (e) => {
    const file = e.target.files[0]
    if (file) validateAndSelect(file)
  }

  const handleUpload = async () => {
    if (!selectedFile) return
    await onUpload(selectedFile, excludePages.trim())
    setSelectedFile(null)
    setExcludePages('')
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <section className="space-y-3">
      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-[var(--radius-card)] text-center cursor-pointer transition-theme ${
          compact ? 'p-4' : 'p-8'
        } ${
          dragOver
            ? 'border-[var(--color-accent)] bg-[var(--color-accent-subtle)]'
            : 'border-[var(--color-border-strong)] hover:border-[var(--color-accent)] hover:bg-[var(--color-accent-subtle)]'
        }`}
      >
        <input ref={inputRef} type="file" accept=".pdf" onChange={handleFileChange} className="hidden" />
        {selectedFile ? (
          <div>
            <p className="text-[14px] text-[var(--color-text-primary)] font-medium">{selectedFile.name}</p>
            <p className="text-[12px] text-[var(--color-text-tertiary)] mt-1">
              {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
            </p>
          </div>
        ) : (
          <div className="space-y-1">
            <Upload size={compact ? 20 : 32} className="mx-auto text-[var(--color-text-tertiary)]" strokeWidth={1.5} />
            {!compact && (
              <>
                <p className="text-[14px] text-[var(--color-text-secondary)]">Drag & drop a PDF, or click to select</p>
                <p className="text-[12px] text-[var(--color-text-tertiary)]">PDF files only, max 50 MB</p>
              </>
            )}
            {compact && <p className="text-[12px] text-[var(--color-text-tertiary)]">Add PDF</p>}
          </div>
        )}
      </div>

      {/* Privacy notice */}
      {!privacyDismissed && (
        <div className="flex items-start gap-2 p-2.5 rounded-[var(--radius-btn)] bg-[var(--color-warning-subtle)] border border-[var(--color-warning)]/20 text-[12px] text-[var(--color-warning)]">
          <Info size={14} className="shrink-0 mt-0.5" />
          <span className="flex-1">
            Content is sent to {llmProvider || 'an external LLM'} for answering.
          </span>
          <button onClick={dismissPrivacy} className="text-[var(--color-warning)] hover:underline shrink-0" aria-label="Dismiss notice">
            Dismiss
          </button>
        </div>
      )}

      {sizeError && (
        <div className="flex items-start gap-2 p-3 rounded-[var(--radius-btn)] bg-[var(--color-danger-subtle)] border border-[var(--color-danger)]/20 text-[14px] text-[var(--color-danger)]">
          <XCircle size={16} className="shrink-0 mt-0.5" />
          <span>{sizeError}</span>
        </div>
      )}

      {selectedFile && (
        <div className="space-y-2">
          <div>
            <label className="block text-[12px] text-[var(--color-text-tertiary)] mb-1">
              Exclude pages (optional)
            </label>
            <input
              type="text" value={excludePages}
              onChange={(e) => setExcludePages(e.target.value)}
              placeholder="e.g. 3, 4"
              className="w-full border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-primary)] rounded-[var(--radius-input)] px-3 py-2 text-[14px] placeholder-[var(--color-text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]"
            />
          </div>
          <button
            onClick={handleUpload}
            disabled={isUploading}
            className="w-full bg-[var(--color-accent)] text-[var(--color-text-inverse)] py-2.5 px-4 rounded-[var(--radius-btn)] hover:bg-[var(--color-accent-hover)] disabled:opacity-50 transition-theme font-medium text-[14px] flex items-center justify-center gap-2"
          >
            {isUploading && <Loader2 size={16} className="animate-spin" />}
            {isUploading ? 'Processing...' : 'Upload & Process'}
          </button>
        </div>
      )}

      {isUploading && uploadProgress != null && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-[12px] text-[var(--color-text-tertiary)] mb-1">
            <span>{uploadProgress < 100 ? 'Uploading...' : 'Processing document...'}</span>
            <span>{uploadProgress < 100 ? `${uploadProgress}%` : ''}</span>
          </div>
          <div className="h-1.5 bg-[var(--color-surface-tertiary)] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-300 ${uploadProgress >= 100 ? 'bg-[var(--color-accent)] animate-pulse' : 'bg-[var(--color-accent)]'}`}
              style={{ width: uploadProgress < 100 ? `${uploadProgress}%` : '100%' }}
            />
          </div>
          {uploadProgress >= 100 && (
            <div className="text-[11px] text-[var(--color-text-tertiary)] space-y-1">
              <p className="flex items-center gap-2"><Loader2 size={10} className="animate-spin" /> Classifying pages...</p>
              <p className="flex items-center gap-2 text-[var(--color-text-quaternary)]">Reading page images (visual pages)</p>
              <p className="flex items-center gap-2 text-[var(--color-text-quaternary)]">Transcribing content</p>
              <p className="flex items-center gap-2 text-[var(--color-text-quaternary)]">Creating embeddings</p>
            </div>
          )}
        </div>
      )}

      {uploadStatus && (
        <div className={`flex items-start gap-2 p-3 rounded-[var(--radius-btn)] text-[14px] ${
          uploadStatus.success
            ? 'bg-[var(--color-success-subtle)] text-[var(--color-success)] border border-[var(--color-success)]/20'
            : 'bg-[var(--color-danger-subtle)] text-[var(--color-danger)] border border-[var(--color-danger)]/20'
        }`}>
          {uploadStatus.success ? <CheckCircle2 size={16} className="shrink-0 mt-0.5" /> : <XCircle size={16} className="shrink-0 mt-0.5" />}
          <div>
            <span>{uploadStatus.message}</span>
            {uploadStatus.warnings?.map((w, i) => (
              <p key={i} className="text-[12px] text-[var(--color-warning)] mt-1">Warning: {w}</p>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

export default UploadSection
