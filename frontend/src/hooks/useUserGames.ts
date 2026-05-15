import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listUserGames, addUserGame, updateUserGame, removeUserGame, steamPreview, steamImport, psnPreview, psnImport, xboxPreview, xboxImport } from '@/api/userGames'
import type { SteamConfirmItem, PSNConfirmItem, XboxConfirmItem } from '@/api/userGames'
import type { UserGameStatus } from '@/types/userGame'

const KEYS = { all: ['user-games'] as const }

export function useUserGames() {
  return useQuery({ queryKey: KEYS.all, queryFn: () => listUserGames() })
}

export function useAddUserGame() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: addUserGame,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all }),
  })
}

export function useUpdateUserGame() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: string } & Partial<{
      status: UserGameStatus; user_rating: number; review: string; hours_played: number
    }>) => updateUserGame(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all }),
  })
}

export function useRemoveUserGame() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => removeUserGame(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all }),
  })
}

export function useSteamPreview() {
  return useMutation({ mutationFn: (profile: string) => steamPreview(profile) })
}

export function useSteamImport() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (items: SteamConfirmItem[]) => steamImport(items),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all }),
  })
}

export function usePSNPreview() {
  return useMutation({ mutationFn: (online_id: string) => psnPreview(online_id) })
}

export function usePSNImport() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (items: PSNConfirmItem[]) => psnImport(items),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all }),
  })
}

export function useXboxPreview() {
  return useMutation({ mutationFn: (gamertag: string) => xboxPreview(gamertag) })
}

export function useXboxImport() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (items: XboxConfirmItem[]) => xboxImport(items),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all }),
  })
}
