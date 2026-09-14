export interface ChatMessage {
  id?: string
  role: 'user' | 'assistant'
  content: string
  created_at?: string
}

export interface AssistantConversation {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface AssistantConversationDetail extends AssistantConversation {
  messages: ChatMessage[]
}

export interface ChatResponse {
  reply: string
  conversation_id: string
}
