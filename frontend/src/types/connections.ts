export type ConnectionProvider = 'demo-pay' | 'grow' | 'cardcom'

export interface ConnectionEventCounts {
  received: number
  processed: number
  duplicate: number
  failed: number
  rejected: number
}

export interface Connection {
  id: string
  provider: ConnectionProvider
  name: string
  enabled: boolean
  webhook_path: string
  has_received_event: boolean
  last_event_at: string | null
  created_at: string
  event_counts: ConnectionEventCounts
  // Cardcom only — not sensitive, shown so the owner can confirm which
  // terminal a connection maps to. Always null for every other provider.
  cardcom_terminal_number: string | null
}

export interface ConnectionWithSecret extends Connection {
  signing_secret: string | null
}

export interface WebhookEventRead {
  id: string
  status: 'received' | 'processed' | 'duplicate' | 'failed' | 'rejected'
  received_at: string
  processed_at: string | null
  failure_category: string | null
  failure_message: string | null
  sale_id: string | null
  can_reprocess: boolean
}

export interface WebhookEventListResponse {
  events: WebhookEventRead[]
  counts: ConnectionEventCounts
}
