import { useState, useMemo } from 'react'
import { useUserGames, useRemoveUserGame } from '@/hooks/useUserGames'
import { useLibraryPrefs } from '@/hooks/useLibraryPrefs'
import { sortGames } from '@/lib/sortGames'
import GameCard from '@/components/library/GameCard'
import SortPills from '@/components/library/SortPills'
import FiltersPopover from '@/components/library/FiltersPopover'
import AddGameModal from '@/components/library/AddGameModal'
import EditGameModal from '@/components/library/EditGameModal'
import GameContextMenu from '@/components/library/GameContextMenu'
import ConfirmModal from '@/components/ui/ConfirmModal'
import type { UserGameRead } from '@/types/userGame'

interface Props {
  onClose: () => void
}

export default function LibraryPanel({ onClose }: Props) {
  const { data: games = [], isLoading } = useUserGames()
  const { prefs, setSortKey, setView, setFilters } = useLibraryPrefs()
  const [search, setSearch] = useState('')
  const [addOpen, setAddOpen] = useState(false)
  const [contextMenu, setContextMenu] = useState<{ userGame: UserGameRead; x: number; y: number } | null>(null)
  const [editGame, setEditGame] = useState<UserGameRead | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<UserGameRead | null>(null)

  const removeMutation = useRemoveUserGame()

  const availableGenres = useMemo(() => {
    const seen = new Map<number, string>()
    games.forEach(ug => ug.game.genres.forEach(g => seen.set(g.id, g.name)))
    return Array.from(seen.entries()).map(([id, name]) => ({ id, name }))
  }, [games])

  const filtered = useMemo(() => {
    let base = games
    const q = search.toLowerCase()
    if (q) base = base.filter(g => g.game.title.toLowerCase().includes(q))
    if (prefs.statusFilter.length)
      base = base.filter(g => g.status !== null && prefs.statusFilter.includes(g.status))
    if (prefs.genreFilter.length)
      base = base.filter(g => g.game.genres.some(genre => prefs.genreFilter.includes(genre.id)))
    return sortGames(base, prefs.sortKey, prefs.sortDir)
  }, [games, search, prefs.sortKey, prefs.sortDir, prefs.statusFilter, prefs.genreFilter])

  const handleMenu = (e: React.MouseEvent, userGame: UserGameRead) => {
    e.preventDefault()
    setContextMenu({ userGame, x: e.clientX, y: e.clientY })
  }

  const handleRequestDelete = () => {
    setConfirmDelete(editGame)
    setEditGame(null)
  }

  const handleConfirmDelete = () => {
    if (!confirmDelete) return
    removeMutation.mutate(confirmDelete.id, { onSuccess: () => setConfirmDelete(null) })
  }

  const activeFiltersCount = prefs.statusFilter.length + prefs.genreFilter.length

  return (
    <aside className="flex w-[350px] flex-shrink-0 flex-col border-l border-border bg-elevated">

      {/* Header */}
      <div className="flex h-[60px] flex-shrink-0 items-center justify-between border-b border-border px-5">
        <div className="flex items-center gap-2.5">
          <span className="text-[14px] font-semibold text-primary">Ma bibliothèque</span>
          <span className="rounded-full bg-panel px-2 py-0.5 text-[11px] font-medium text-muted">
            {games.length}
          </span>
        </div>
        <button
          onClick={onClose}
          className="flex h-8 w-8 items-center justify-center rounded-[6px] text-[13px] text-muted transition-colors hover:bg-hover hover:text-primary"
          aria-label="Fermer"
        >
          ✕
        </button>
      </div>

      {/* Search */}
      <div className="flex-shrink-0 border-b border-border px-4 py-3">
        <input
          type="search"
          placeholder="Rechercher un jeu…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full rounded-[8px] border border-border bg-input-bg px-4 py-2.5 text-[13px] text-primary outline-none placeholder:text-faint transition-colors focus:border-accent/40"
        />
      </div>

      {/* Sort + filter row */}
      <div className="flex flex-shrink-0 items-center gap-2 border-b border-border px-4 py-2.5">
        <SortPills
          value={prefs.sortKey}
          dir={prefs.sortDir}
          onChange={setSortKey}
        />
        <FiltersPopover
          statusValue={prefs.statusFilter}
          genreValue={prefs.genreFilter}
          availableGenres={availableGenres}
          onChange={setFilters}
        />
        {activeFiltersCount > 0 && (
          <button
            onClick={() => setFilters([], [])}
            className="text-[11px] text-faint transition-colors hover:text-muted"
          >
            ✕
          </button>
        )}
        <div className="ml-auto flex shrink-0 overflow-hidden rounded-[6px] border border-border">
          {(['compact', 'detailed'] as const).map(v => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={[
                'px-2.5 py-1.5 text-[12px] leading-none transition-all',
                prefs.view === v ? 'bg-accent-dim text-accent-soft' : 'text-faint hover:bg-hover hover:text-muted',
              ].join(' ')}
              aria-label={v === 'compact' ? 'Vue compacte' : 'Vue détaillée'}
            >
              {v === 'compact' ? '☰' : '⊞'}
            </button>
          ))}
        </div>
      </div>

      {/* Game list */}
      <div className="flex flex-1 flex-col overflow-y-auto px-3 py-3">
        {isLoading && (
          <div className="flex flex-1 items-center justify-center text-[13px] text-muted">
            Chargement…
          </div>
        )}
        {!isLoading && filtered.length === 0 && (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
            <span className="text-[28px] opacity-20">🎮</span>
            <p className="text-[13px] text-muted">
              {search || activeFiltersCount > 0 ? 'Aucun résultat' : 'Bibliothèque vide'}
            </p>
            {!search && activeFiltersCount === 0 && (
              <button
                onClick={() => setAddOpen(true)}
                className="mt-1 flex items-center gap-1.5 rounded-[8px] bg-accent px-4 py-2 text-[12px] font-semibold text-white shadow-[0_0_12px_rgba(16,53,192,0.3)] transition-colors hover:bg-accent/90"
              >
                <span className="text-[14px] leading-none">＋</span>
                Ajouter ton premier jeu
              </button>
            )}
          </div>
        )}
        <div className="flex flex-col gap-1">
          {filtered.map(ug => (
            <GameCard key={ug.id} userGame={ug} detailed={prefs.view === 'detailed'} onMenu={handleMenu} />
          ))}
        </div>
      </div>

      {/* Sticky footer button */}
      {!isLoading && filtered.length > 0 && (
        <div className="flex-shrink-0 border-t border-border bg-panel px-3 py-2.5">
          <button
            onClick={() => setAddOpen(true)}
            className="flex w-full items-center justify-center gap-2 rounded-[8px] border border-accent/35 bg-accent-dim py-2 text-[12px] font-semibold text-accent-soft transition-colors hover:border-accent/55 hover:bg-[rgba(16,53,192,0.2)] hover:text-white"
          >
            <span className="text-[14px] leading-none">＋</span>
            Ajouter un jeu
          </button>
        </div>
      )}

      <AddGameModal open={addOpen} onClose={() => setAddOpen(false)} />

      {contextMenu && (
        <GameContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          onEdit={() => setEditGame(contextMenu.userGame)}
          onDelete={() => setConfirmDelete(contextMenu.userGame)}
          onClose={() => setContextMenu(null)}
        />
      )}

      <EditGameModal
        open={editGame !== null}
        userGame={editGame}
        onClose={() => setEditGame(null)}
        onRequestDelete={handleRequestDelete}
      />

      <ConfirmModal
        open={confirmDelete !== null}
        title={`Retirer ${confirmDelete?.game.title ?? ''} ?`}
        message="Ce jeu sera retiré de ta bibliothèque. Ta note, tes heures jouées et ta critique seront perdues. Cette action est irréversible."
        confirmLabel="Supprimer"
        danger
        onConfirm={handleConfirmDelete}
        onCancel={() => setConfirmDelete(null)}
      />
    </aside>
  )
}
