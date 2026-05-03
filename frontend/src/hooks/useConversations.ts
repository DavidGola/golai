import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listConversations,
  getConversation,
  createConversation,
  renameConversation,
  deleteConversation,
} from '@/api/conversations'

const KEYS = {
  list: ['conversations'] as const,
  detail: (id: string) => ['conversations', id] as const,
}

export function useConversationsList() {
  return useQuery({ queryKey: KEYS.list, queryFn: listConversations })
}

export function useConversation(id: string | undefined) {
  return useQuery({
    queryKey: KEYS.detail(id ?? ''),
    queryFn: () => getConversation(id!),
    enabled: !!id,
  })
}

export function useCreateConversation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (title?: string) => createConversation(title),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.list }),
  })
}

export function useRenameConversation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      renameConversation(id, title),
    onSuccess: (_data, { id }) => {
      qc.invalidateQueries({ queryKey: KEYS.list })
      qc.invalidateQueries({ queryKey: KEYS.detail(id) })
    },
  })
}

export function useDeleteConversation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteConversation(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.list }),
  })
}
