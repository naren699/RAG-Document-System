import { Sun, Moon, Monitor } from 'lucide-react'

function getModelShortName(info) {
  if (!info) return null
  const model = info.llm_model || ''
  const provider = info.llm_provider || ''

  const names = {
    'gemini-3.8-flash': 'Gemini 3.8 Flash',
    'gemini-2.5-flash-preview': 'Gemini 2.5 Flash',
    'claude-sonnet-4-20250514': 'Claude Sonnet 4',
    'google/gemini-3.8-flash': 'Gemini 3.8 Flash',
    'google/gemini-2.5-flash-preview': 'Gemini 2.5 Flash',
  }

  const short = names[model] || model
  const via = provider === 'openrouter' ? ' via OpenRouter' : ''
  return short + via
}

function ThemeToggle({ theme, onToggle }) {
  const nextLabel = theme === 'system' ? 'Light' : theme === 'light' ? 'Dark' : 'System'

  return (
    <button
      onClick={onToggle}
      className="p-2 rounded-[var(--radius-btn)] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-tertiary)] transition-theme"
      aria-label={`Switch to ${nextLabel} theme`}
      title={`Theme: ${theme}. Click for ${nextLabel}`}
    >
      {theme === 'light' && <Sun size={18} strokeWidth={1.75} />}
      {theme === 'dark' && <Moon size={18} strokeWidth={1.75} />}
      {theme === 'system' && <Monitor size={18} strokeWidth={1.75} />}
    </button>
  )
}

function Header({ providerInfo, theme, onToggleTheme, activeTab, onTabChange }) {
  const modelName = getModelShortName(providerInfo)

  return (
    <header className="h-14 border-b border-[var(--color-border)] bg-[var(--color-surface)] flex items-center justify-between px-4 lg:px-6 shrink-0 transition-theme">
      {/* Left: logo + title */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-[var(--radius-btn)] bg-[var(--color-accent)] flex items-center justify-center">
          <span className="text-[var(--color-text-inverse)] text-sm font-bold leading-none">F</span>
        </div>
        <div className="flex items-center gap-2">
          <h1 className="text-[20px] font-semibold text-[var(--color-text-primary)] leading-none">FARE</h1>
          <span className="hidden sm:inline text-[12px] text-[var(--color-text-tertiary)]">Document Q&A</span>
        </div>
      </div>

      {/* Center: tabs */}
      <nav className="flex items-center gap-1" role="tablist" aria-label="Main navigation">
        <button
          role="tab"
          aria-selected={activeTab === 'ask'}
          onClick={() => onTabChange('ask')}
          className={`px-4 py-1.5 text-[14px] font-medium rounded-[var(--radius-btn)] transition-theme ${
            activeTab === 'ask'
              ? 'bg-[var(--color-accent-subtle)] text-[var(--color-accent)]'
              : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-tertiary)]'
          }`}
        >
          Ask
        </button>
        <button
          role="tab"
          aria-selected={activeTab === 'evaluate'}
          onClick={() => onTabChange('evaluate')}
          className={`px-4 py-1.5 text-[14px] font-medium rounded-[var(--radius-btn)] transition-theme ${
            activeTab === 'evaluate'
              ? 'bg-[var(--color-accent-subtle)] text-[var(--color-accent)]'
              : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-tertiary)]'
          }`}
        >
          Evaluate
        </button>
      </nav>

      {/* Right: model chip + theme */}
      <div className="flex items-center gap-2">
        {modelName && (
          <span className="hidden md:inline-flex text-[12px] text-[var(--color-text-tertiary)] bg-[var(--color-surface-tertiary)] px-2.5 py-1 rounded-full leading-none">
            {modelName}
          </span>
        )}
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
      </div>
    </header>
  )
}

export default Header
