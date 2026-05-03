import { apiClient } from '@/lib/apiClient'
import {
  ConversationReadSchema,
  ConversationWithMessagesSchema,
  type ConversationRead,
  type ConversationWithMessages,
} from '@/types/conversation'
import { z } from 'zod'

export async function listConversations(): Promise<ConversationRead[]> {
  const res = await apiClient.get<unknown>('/conversations')
  return z.array(ConversationReadSchema).parse(res.data)
}

export async function getConversation(id: string): Promise<ConversationWithMessages> {
  const res = await apiClient.get<unknown>(`/conversations/${id}`)
  return ConversationWithMessagesSchema.parse(res.data)
}

export async function createConversation(title?: string): Promise<ConversationRead> {
  const res = await apiClient.post<unknown>('/conversations', { title: title ?? null })
  return ConversationReadSchema.parse(res.data)
}

export async function renameConversation(id: string, title: string): Promise<ConversationRead> {
  const res = await apiClient.patch<unknown>(`/conversations/${id}`, { title })
  return ConversationReadSchema.parse(res.data)
}

export async function deleteConversation(id: string): Promise<void> {
  await apiClient.delete(`/conversations/${id}`)
}
