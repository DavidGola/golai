import { apiClient } from '@/lib/apiClient'
import { UserGameReadSchema, UserGameStatusSchema, type UserGameRead, type UserGameStatus } from '@/types/userGame'
import { z } from 'zod'

export const SteamPreviewItemSchema = z.object({
  game_id: z.string(),
  title: z.string(),
  cover_url: z.string().nullable(),
  hours_on_record: z.number().nullable(),
  suggested_status: UserGameStatusSchema.nullable(),
  already_in_library: z.boolean(),
})
export type SteamPreviewItem = z.infer<typeof SteamPreviewItemSchema>

export type SteamConfirmItem = {
  game_id: string
  status: UserGameStatus | null
  user_rating: number | null
  review: string | null
  hours_on_record: number | null
}

export async function steamPreview(profile: string): Promise<SteamPreviewItem[]> {
  const res = await apiClient.post<unknown>('/users/me/games/steam/preview', { profile })
  return z.object({ items: z.array(SteamPreviewItemSchema) }).parse(res.data).items
}

export async function steamImport(items: SteamConfirmItem[]): Promise<{ imported: number; skipped: number }> {
  const res = await apiClient.post<unknown>('/users/me/games/steam/import', { items })
  return z.object({ imported: z.number(), skipped: z.number() }).parse(res.data)
}

export async function listUserGames(status?: UserGameStatus): Promise<UserGameRead[]> {
  const res = await apiClient.get<unknown>('/users/me/games', {
    params: status ? { status } : {},
  })
  return z.array(UserGameReadSchema).parse(res.data)
}

export async function addUserGame(payload: {
  game_id: string
  status?: UserGameStatus
  user_rating?: number
  review?: string
  hours_played?: number
}): Promise<UserGameRead> {
  const res = await apiClient.post<unknown>('/users/me/games', payload)
  return UserGameReadSchema.parse(res.data)
}

export async function updateUserGame(
  id: string,
  payload: Partial<{
    status: UserGameStatus
    user_rating: number
    review: string
    hours_played: number
  }>,
): Promise<UserGameRead> {
  const res = await apiClient.patch<unknown>(`/users/me/games/${id}`, payload)
  return UserGameReadSchema.parse(res.data)
}

export async function removeUserGame(id: string): Promise<void> {
  await apiClient.delete(`/users/me/games/${id}`)
}

export const PSNPreviewItemSchema = z.object({
  game_id: z.string(),
  title: z.string(),
  cover_url: z.string().nullable(),
  trophy_progress_pct: z.number().nullable(),
  hours_played: z.number().nullable(),
  suggested_status: UserGameStatusSchema.nullable(),
  already_in_library: z.boolean(),
})
export type PSNPreviewItem = z.infer<typeof PSNPreviewItemSchema>

export type PSNConfirmItem = {
  game_id: string
  status: UserGameStatus | null
  user_rating: number | null
  review: string | null
  hours_played: number | null
}

export async function psnPreview(online_id: string): Promise<PSNPreviewItem[]> {
  const res = await apiClient.post<unknown>('/users/me/games/psn/preview', { online_id })
  return z.object({ items: z.array(PSNPreviewItemSchema) }).parse(res.data).items
}

export async function psnImport(items: PSNConfirmItem[]): Promise<{ imported: number; skipped: number }> {
  const res = await apiClient.post<unknown>('/users/me/games/psn/import', { items })
  return z.object({ imported: z.number(), skipped: z.number() }).parse(res.data)
}

export const XboxPreviewItemSchema = z.object({
  game_id: z.string(),
  title: z.string(),
  cover_url: z.string().nullable(),
  achievement_progress_pct: z.number().nullable(),
  suggested_status: UserGameStatusSchema.nullable(),
  already_in_library: z.boolean(),
})
export type XboxPreviewItem = z.infer<typeof XboxPreviewItemSchema>

export type XboxConfirmItem = {
  game_id: string
  status: UserGameStatus | null
  user_rating: number | null
  review: string | null
}

export async function xboxPreview(gamertag: string): Promise<XboxPreviewItem[]> {
  const res = await apiClient.post<unknown>('/users/me/games/xbox/preview', { gamertag })
  return z.object({ items: z.array(XboxPreviewItemSchema) }).parse(res.data).items
}

export async function xboxImport(items: XboxConfirmItem[]): Promise<{ imported: number; skipped: number }> {
  const res = await apiClient.post<unknown>('/users/me/games/xbox/import', { items })
  return z.object({ imported: z.number(), skipped: z.number() }).parse(res.data)
}
