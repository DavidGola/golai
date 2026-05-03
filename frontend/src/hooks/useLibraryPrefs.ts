import { useState, useEffect } from 'react'
import type { SortKey, SortDir } from '@/lib/sortGames'
import type { UserGameStatus } from '@/types/userGame'

export type ViewMode = 'compact' | 'detailed'

export interface LibraryPrefs {
  sortKey: SortKey
  sortDir: SortDir
  view: ViewMode
  statusFilter: UserGameStatus[]
  genreFilter: number[]
}

const STORAGE_KEY = 'golai.library.prefs.v1'

const DEFAULTS: LibraryPrefs = {
  sortKey: 'rating',
  sortDir: 'desc',
  view: 'compact',
  statusFilter: [],
  genreFilter: [],
}

const VALID_SORT_KEYS: SortKey[] = ['rating', 'playtime', 'steam', 'release', 'title']

function load(): LibraryPrefs {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULTS
    const parsed = { ...DEFAULTS, ...JSON.parse(raw) }
    if (!VALID_SORT_KEYS.includes(parsed.sortKey)) parsed.sortKey = DEFAULTS.sortKey
    return parsed
  } catch {
    return DEFAULTS
  }
}

export function useLibraryPrefs() {
  const [prefs, setPrefs] = useState<LibraryPrefs>(load)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
  }, [prefs])

  const setSortKey = (key: SortKey, dir: SortDir) =>
    setPrefs(p => ({ ...p, sortKey: key, sortDir: dir }))

  const setView = (view: ViewMode) =>
    setPrefs(p => ({ ...p, view }))

  const setFilters = (statusFilter: UserGameStatus[], genreFilter: number[]) =>
    setPrefs(p => ({ ...p, statusFilter, genreFilter }))

  return { prefs, setSortKey, setView, setFilters }
}
