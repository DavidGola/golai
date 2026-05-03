import type { UserGameRead } from '@/types/userGame'

export type SortKey = 'rating' | 'playtime' | 'steam' | 'release' | 'title'
export type SortDir = 'asc' | 'desc'

export const SORT_LABELS: Record<SortKey, string> = {
  rating:   '★ Note',
  playtime: '⏱ Heures',
  steam:    '🟦 Steam',
  release:  '🗓 Sortie',
  title:    '🔤 Titre',
}

export const SORT_DEFAULT_DIR: Record<SortKey, SortDir> = {
  rating:   'desc',
  playtime: 'desc',
  steam:    'desc',
  release:  'desc',
  title:    'asc',
}

function getValue(ug: UserGameRead, key: SortKey): number | string | null {
  switch (key) {
    case 'rating':   return ug.user_rating
    case 'playtime': return ug.hours_played
    case 'steam':    return ug.game.steam_score
    case 'release':  return ug.game.release_date ? new Date(ug.game.release_date).getTime() : null
    case 'title':    return ug.game.title.toLowerCase()
  }
}

export function sortGames(games: UserGameRead[], key: SortKey, dir: SortDir): UserGameRead[] {
  return [...games].sort((a, b) => {
    const va = getValue(a, key)
    const vb = getValue(b, key)

    // nulls always last regardless of direction
    if (va === null && vb === null) return 0
    if (va === null) return 1
    if (vb === null) return -1

    let cmp: number
    if (typeof va === 'string' && typeof vb === 'string') {
      cmp = va.localeCompare(vb)
    } else {
      cmp = (va as number) - (vb as number)
    }

    return dir === 'asc' ? cmp : -cmp
  })
}
