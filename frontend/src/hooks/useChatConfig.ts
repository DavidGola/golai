import { useQuery } from '@tanstack/react-query'
import { getChatConfig } from '@/api/chatConfig'

export function useChatConfig() {
  return useQuery({
    queryKey: ['chat-config'],
    queryFn: getChatConfig,
  })
}
