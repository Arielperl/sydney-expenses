import { apiClient, toApiError } from './apiClient'
import type { AssistantConversation, AssistantConversationDetail, ChatResponse } from '../types/assistant'

export async function listAssistantConversations(): Promise<AssistantConversation[]> {
  try {
    return (await apiClient.get<AssistantConversation[]>('/assistant/conversations')).data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function getAssistantConversation(id: string): Promise<AssistantConversationDetail> {
  try {
    return (await apiClient.get<AssistantConversationDetail>(`/assistant/conversations/${id}`)).data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function deleteAssistantConversation(id: string): Promise<void> {
  try {
    await apiClient.delete(`/assistant/conversations/${id}`)
  } catch (error) {
    throw toApiError(error)
  }
}

export async function renameAssistantConversation(id: string, title: string): Promise<AssistantConversation> {
  try {
    return (await apiClient.patch<AssistantConversation>(`/assistant/conversations/${id}`, { title })).data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function sendChatMessage(
  message: string,
  conversationId: string | null,
): Promise<ChatResponse> {
  try {
    return (
      await apiClient.post<ChatResponse>('/assistant/chat', {
        message,
        conversation_id: conversationId,
      })
    ).data
  } catch (error) {
    throw toApiError(error)
  }
}
