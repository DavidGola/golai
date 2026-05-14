import { z } from 'zod'
import { ProposalReadSchema } from '@/types/proposal'
import { CitedGameSchema } from '@/types/store'

export const MessageReadSchema = z.object({
  id: z.string(),
  role: z.enum(['user', 'assistant']),
  content: z.string(),
  tokens_used: z.number().nullable(),
  cited_games: z.array(CitedGameSchema).nullable().optional(),
  created_at: z.string(),
  proposals: z.array(ProposalReadSchema).default([]),
})

export const ConversationReadSchema = z.object({
  id: z.string(),
  title: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
})

export const ConversationWithMessagesSchema = ConversationReadSchema.extend({
  messages: z.array(MessageReadSchema),
})

export type MessageRead = z.infer<typeof MessageReadSchema>
export type ConversationRead = z.infer<typeof ConversationReadSchema>
export type ConversationWithMessages = z.infer<typeof ConversationWithMessagesSchema>
