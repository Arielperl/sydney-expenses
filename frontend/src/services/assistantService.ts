import { apiClient, toApiError } from './apiClient'
import type { ChatMessage } from '../types/assistant'

export async function sendChatMessage(message: string, history: ChatMessage[]): Promise<string> {
  try {
    const response = await apiClient.post<{ reply: string }>('/assistant/chat', { message, history })
    return response.data.reply
  } catch (error) {
    throw toApiError(error)
  }
}
