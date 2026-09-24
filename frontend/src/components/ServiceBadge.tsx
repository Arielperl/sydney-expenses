import { colorForService } from '../lib/serviceColors'

/** Neutral chip with a per-service colour dot: the text stays high-contrast in both themes. */
export function ServiceBadge({ serviceName }: { serviceName: string }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
      <span aria-hidden="true" className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: colorForService(serviceName) }} />
      <span className="truncate">{serviceName}</span>
    </span>
  )
}
