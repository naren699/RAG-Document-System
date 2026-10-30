export function pluralize(n, word) {
  return n === 1 ? `1 ${word}` : `${n} ${word}s`
}
