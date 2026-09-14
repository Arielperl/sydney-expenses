export type IntegrationConnection = {
  id: string
  provider: string
  name: string
  enabled: boolean
  webhook_path: string
  last_event_at: string | null
  created_at: string
}

export type ConnectionWithSecret = IntegrationConnection & {
  signing_secret: string
}
