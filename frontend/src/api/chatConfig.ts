import { z } from 'zod'
import { apiClient } from '@/lib/apiClient'

const ChatConfigSchema = z.object({
  model: z.string(),
})

export type ChatConfig = z.infer<typeof ChatConfigSchema>

export async function getChatConfig(): Promise<ChatConfig> {
  const res = await apiClient.get<unknown>('/chat/config')
  return ChatConfigSchema.parse(res.data)
}
