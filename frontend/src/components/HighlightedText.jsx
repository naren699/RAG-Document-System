const STOPWORDS = new Set([
  'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
  'what', 'which', 'who', 'whom', 'how', 'when', 'where', 'why',
  'do', 'does', 'did', 'in', 'on', 'at', 'of', 'to', 'for', 'with',
  'and', 'or', 'not', 'no', 'nor', 'this', 'that', 'it', 'its',
  'by', 'from', 'as', 'but', 'so', 'if', 'has', 'have', 'had',
  'can', 'could', 'would', 'should', 'will', 'shall', 'may', 'might', 'must',
  'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
  'between', 'under', 'over', 'than', 'then', 'each', 'every',
  'all', 'any', 'some', 'such',
])

function stemBasic(word) {
  const lower = word.toLowerCase()
  if (lower.endsWith('ing') && lower.length > 5) return lower.slice(0, -3)
  if (lower.endsWith('tion') && lower.length > 5) return lower.slice(0, -4)
  if (lower.endsWith('es') && lower.length > 4) return lower.slice(0, -2)
  if (lower.endsWith('s') && !lower.endsWith('ss') && lower.length > 3) return lower.slice(0, -1)
  if (lower.endsWith('ed') && lower.length > 4) return lower.slice(0, -2)
  return lower
}

export function extractQueryKeywords(query) {
  if (!query?.trim()) return []
  return query.trim().split(/\s+/)
    .filter(w => w.length > 2 && !STOPWORDS.has(w.toLowerCase()))
}

function HighlightedText({ text, query }) {
  if (!query?.trim() || !text) return <span>{text}</span>

  const words = extractQueryKeywords(query)

  if (!words.length) return <span>{text}</span>

  const stems = words.map(w => stemBasic(w))
  const allForms = [...new Set([...words, ...stems].filter(w => w.length > 2))]

  const escaped = allForms.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const pattern = new RegExp(`\\b(${escaped.join('|')})\\b`, 'gi')
  const parts = text.split(pattern)

  return (
    <span>
      {parts.map((part, i) =>
        i % 2 === 1
          ? <mark key={i} className="bg-yellow-200 rounded px-0.5">{part}</mark>
          : <span key={i}>{part}</span>
      )}
    </span>
  )
}

export default HighlightedText
