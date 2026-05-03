import { z } from 'zod'
import { GameListItemSchema } from '@/types/userGame'

export const GameReadSchema = GameListItemSchema.extend({
  summary: z.string().nullable(),
  storyline: z.string().nullable(),
  developer: z.string().nullable(),
  steam_description: z.string().nullable(),
  steam_reviews_summary: z.string().nullable(),
  hltb_extra: z.number().nullable(),
  hltb_completionist: z.number().nullable(),
  opencritic_excerpts: z.array(z.string()).nullable(),
  keywords: z.array(z.string()).nullable(),
  modes: z.array(z.object({ id: z.number(), slug: z.string(), name: z.string() })),
  tags: z.array(z.object({ id: z.number(), slug: z.string(), name: z.string() })),
})

export const GameListResponseSchema = z.object({
  items: z.array(GameListItemSchema),
  total: z.number(),
  page: z.number(),
  page_size: z.number(),
})

export type GameRead = z.infer<typeof GameReadSchema>
export type GameListResponse = z.infer<typeof GameListResponseSchema>
