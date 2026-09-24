// Muted, mid-luminance hues that read on white and on the dark surface, and
// sit comfortably beside Sydney's teal instead of competing with it.
const PALETTE = [
  '#26957a',
  '#3b6fb6',
  '#c98a1b',
  '#8a5a9e',
  '#b5543c',
  '#5b7083',
  '#7a8a3a',
  '#2c8ea3',
  '#b24c6a',
  '#5a5fb0',
]

// Service/product names are free text, not a fixed enum — colors are
// assigned by a stable hash of the string so the same service always gets
// the same color across renders, without needing a registry of known names.
export function colorForService(serviceName: string): string {
  let hash = 0
  for (let i = 0; i < serviceName.length; i++) {
    hash = (hash << 5) - hash + serviceName.charCodeAt(i)
    hash |= 0
  }
  const index = Math.abs(hash) % PALETTE.length
  return PALETTE[index]
}
