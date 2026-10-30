import { X, PanelLeftClose } from 'lucide-react'
import { useEffect, useRef } from 'react'

function Sidebar({ open, onClose, children }) {
  const overlayRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const handleKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open, onClose])

  return (
    <>
      {/* Desktop sidebar — always visible */}
      <aside aria-label="Documents and settings" className="hidden lg:flex flex-col w-[var(--sidebar-width)] border-r border-[var(--color-border)] bg-[var(--color-surface)] shrink-0 overflow-hidden transition-theme">
        <div className="flex-1 overflow-y-auto sidebar-scroll p-4 space-y-4">
          {children}
        </div>
      </aside>

      {/* Mobile/tablet drawer */}
      {open && (
        <div
          ref={overlayRef}
          className="fixed inset-0 z-40 lg:hidden"
          onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
        >
          <div className="absolute inset-0 bg-black/40 transition-opacity" />
          <aside role="dialog" aria-modal="true" aria-label="Documents sidebar" className="absolute inset-y-0 left-0 w-[min(var(--sidebar-width),85vw)] bg-[var(--color-surface)] shadow-lg flex flex-col transition-theme">
            <div className="flex items-center justify-between h-14 px-4 border-b border-[var(--color-border)]">
              <span className="text-[14px] font-semibold text-[var(--color-text-primary)]">Documents</span>
              <button
                onClick={onClose}
                className="p-2 rounded-[var(--radius-btn)] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-tertiary)]"
                aria-label="Close sidebar"
              >
                <X size={18} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto sidebar-scroll p-4 space-y-4">
              {children}
            </div>
          </aside>
        </div>
      )}
    </>
  )
}

export default Sidebar
