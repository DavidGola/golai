import { apiClient } from '@/lib/apiClient'
import { GameListResponseSchema, GameReadSchema, type GameListResponse, type GameRead } from '@/types/game'

export async function searchGames(params: {
  q?: string
  genre_slug?: string
  platform_slug?: string
  page?: number
  page_size?: number
}): Promise<GameListResponse> {
  const res = await apiClient.get<unknown>('/games', { params })
  return GameListResponseSchema.parse(res.data)
}

export async function getGame(id: number): Promise<GameRead> {
  const res = await apiClient.get<unknown>(`/games/${id}`)
  return GameReadSchema.parse(res.data)
}
