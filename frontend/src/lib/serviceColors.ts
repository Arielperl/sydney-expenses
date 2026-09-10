const PALETTE = [
  '#2563eb',
  '#059669',
  '#d97706',
  '#dc2626',
  '#7c3aed',
  '#0891b2',
  '#db2777',
  '#65a30d',
  '#4f46e5',
  '#64748b',
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
