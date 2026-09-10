import { colorForService } from '../lib/serviceColors'

export function ServiceBadge({ serviceName }: { serviceName: string }) {
  const color = colorForService(serviceName)
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{ backgroundColor: `${color}1a`, color }}
    >
      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      {serviceName}
    </span>
  )
}
