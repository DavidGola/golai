import { z } from 'zod'

export const UserGameStatusSchema = z.enum(['completed', 'todo', 'dropped', 'not_started'])

export const GameListItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  cover_url: z.string().nullable(),
  release_date: z.string().nullable(),
  igdb_rating: z.number().nullable(),
  metacritic_score: z.number().nullable(),
  opencritic_score: z.number().nullable(),
  steam_score: z.number().nullable(),
  steam_id: z.number().nullable(),
  hltb_main: z.number().nullable(),
  genres: z.array(z.object({ id: z.number(), slug: z.string(), name: z.string() })),
  platforms: z.array(z.object({ id: z.number(), slug: z.string(), name: z.string() })),
})

export const UserGameReadSchema = z.object({
  id: z.string(),
  game_id: z.string(),
  status: UserGameStatusSchema.nullable(),
  user_rating: z.number().nullable(),
  review: z.string().nullable(),
  hours_played: z.number().nullable(),
  added_at: z.string(),
  completed_at: z.string().nullable(),
  game: GameListItemSchema,
})

export type UserGameStatus = z.infer<typeof UserGameStatusSchema>
export type GameListItem = z.infer<typeof GameListItemSchema>
export type UserGameRead = z.infer<typeof UserGameReadSchema>
