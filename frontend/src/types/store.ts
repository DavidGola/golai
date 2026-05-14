import { z } from 'zod'

export const STORE_PLATFORMS = ['steam', 'playstation', 'nintendo', 'xbox', 'epic', 'gog'] as const
export type StorePlatform = (typeof STORE_PLATFORMS)[number]

export const StoreLinkSchema = z.object({
  platform: z.enum(STORE_PLATFORMS),
  url: z.string(),
})

export const CitedGameSchema = z.object({
  id: z.string(),
  title: z.string(),
  cover_url: z.string().nullable(),
  store_links: z.array(StoreLinkSchema).default([]),
  platforms: z.array(z.string()).default([]),
})

export type StoreLink = z.infer<typeof StoreLinkSchema>
export type CitedGame = z.infer<typeof CitedGameSchema>
