import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { searchGames } from '@/api/games'
import { useAddUserGame } from '@/hooks/useUserGames'
import type { GameListItem, UserGameStatus } from '@/types/userGame'
import LibraryImportPanel from './LibraryImportPanel'
import { steamSource, psnSource, xboxSource } from './libraryImportSources'

const STATUS_OPTIONS: { value: UserGameStatus; label: string; activeClass: string }[] = [
  { value: 'completed',   label: 'Terminé',   activeClass: 'bg-[rgba(40,200,100,0.12)] text-[#5DE89E] border-[rgba(40,200,100,0.25)]' },
  { value: 'todo',        label: 'À faire',   activeClass: 'bg-[rgba(91,126,255,0.08)] text-muted border-border' },
  { value: 'dropped',     label: 'Abandonné', activeClass: 'bg-danger-dim text-[#FF6B84] border-danger/25' },
  { value: 'not_started', label: 'Intouché',  activeClass: 'bg-[rgba(255,170,50,0.1)] text-[#FFAA32] border-[rgba(255,170,50,0.25)]' },
]

const COVER_GRADIENTS = [
  'linear-gradient(135deg, #1a1a2e, #16213e)',
  'linear-gradient(135deg, #0d1b2a, #1b2838)',
  'linear-gradient(135deg, #1a0a2e, #2a0845)',
  'linear-gradient(135deg, #0a1628, #1a3a5c)',
  'linear-gradient(135deg, #1a1200, #3a2800)',
  'linear-gradient(135deg, #0a1a0a, #1a3a1a)',
  'linear-gradient(135deg, #2a0a0a, #4a1a1a)',
  'linear-gradient(135deg, #1a1a1a, #2e2e2e)',
]
function coverGradient(id: string) {
  const n = parseInt(id.replace(/-/g, '').slice(0, 8), 16)
  return COVER_GRADIENTS[n % COVER_GRADIENTS.length] ?? COVER_GRADIENTS[0]!
}

function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const code = err.response?.data?.detail
    if (err.response?.status === 409 || code === 'game_already_in_library') {
      return 'Ce jeu est déjà dans ta bibliothèque.'
    }
    if (err.response?.status === 404 || code === 'game_not_found') {
      return 'Jeu introuvable dans le catalogue.'
    }
  }
  return 'Impossible d\'ajouter le jeu. Réessaie plus tard.'
}

interface Props {
  open: boolean
  onClose: () => void
}

export default function AddGameModal({ open, onClose }: Props) {
  const [tab, setTab] = useState<'manual' | 'steam' | 'psn' | 'xbox'>('manual')
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [selected, setSelected] = useState<GameListItem | null>(null)
  const [status, setStatus] = useState<UserGameStatus | null>(null)
  const [rating, setRating] = useState<number | null>(null)
  const [hours, setHours] = useState('')
  const [review, setReview] = useState('')

  const addMutation = useAddUserGame()

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query.trim()), 300)
    return () => clearTimeout(t)
  }, [query])

  useEffect(() => {
    if (!open) {
      setTab('manual')
      setQuery('')
      setDebouncedQuery('')
      setSelected(null)
      setStatus(null)
      setRating(null)
      setHours('')
      setReview('')
      addMutation.reset()
    }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  const searchEnabled = debouncedQuery.length >= 2 && !selected
  const { data: searchData, isFetching } = useQuery({
    queryKey: ['games-search', debouncedQuery],
    queryFn: () => searchGames({ q: debouncedQuery, page_size: 6 }),
    enabled: searchEnabled,
  })

  if (!open) return null

  const canSubmit = !!selected && !addMutation.isPending

  const handleSubmit = () => {
    if (!selected) return
    const hoursNum = hours.trim() ? Number(hours) : undefined
    addMutation.mutate(
      {
        game_id: selected.id,
        ...(status ? { status } : {}),
        ...(rating !== null ? { user_rating: rating } : {}),
        ...(review.trim() ? { review: review.trim() } : {}),
        ...(hoursNum !== undefined && !Number.isNaN(hoursNum) ? { hours_played: hoursNum } : {}),
      },
      { onSuccess: () => onClose() },
    )
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="flex max-h-[90vh] w-full max-w-[520px] flex-col overflow-hidden rounded-[16px] border border-border bg-elevated shadow-2xl">

        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-5">
          <h2 className="text-[16px] font-semibold text-primary">Ajouter un jeu</h2>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-[6px] text-muted transition-colors hover:bg-hover hover:text-primary"
            aria-label="Fermer"
          >
            ✕
          </button>
        </div>

        {/* Tabs */}
        <div className="mt-4 flex gap-1 border-b border-border px-6">
          <button
            onClick={() => setTab('manual')}
            className={[
              'flex items-center gap-2 px-4 py-2 text-[13px] font-medium transition-colors',
              tab === 'manual'
                ? 'border-b-2 border-accent-soft text-primary'
                : 'border-b-2 border-transparent text-muted hover:text-primary',
            ].join(' ')}
          >
            <span>✏️</span> Manuel
          </button>
          <button
            onClick={() => setTab('steam')}
            className={[
              'flex items-center gap-2 px-4 py-2 text-[13px] font-medium transition-colors',
              tab === 'steam'
                ? 'border-b-2 border-accent-soft text-primary'
                : 'border-b-2 border-transparent text-muted hover:text-primary',
            ].join(' ')}
          >
            <span>🎮</span> Steam
          </button>
          <button
            onClick={() => setTab('psn')}
            className={[
              'flex items-center gap-2 px-4 py-2 text-[13px] font-medium transition-colors',
              tab === 'psn'
                ? 'border-b-2 border-accent-soft text-primary'
                : 'border-b-2 border-transparent text-muted hover:text-primary',
            ].join(' ')}
          >
            <span>🎮</span> PlayStation
          </button>
          <button
            onClick={() => setTab('xbox')}
            className={[
              'flex items-center gap-2 px-4 py-2 text-[13px] font-medium transition-colors',
              tab === 'xbox'
                ? 'border-b-2 border-accent-soft text-primary'
                : 'border-b-2 border-transparent text-muted hover:text-primary',
            ].join(' ')}
          >
            <span>🎮</span> Xbox
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">

          {tab === 'steam' && (
            <LibraryImportPanel source={steamSource} onDone={onClose} />
          )}

          {tab === 'psn' && (
            <LibraryImportPanel source={psnSource} onDone={onClose} />
          )}

          {tab === 'xbox' && (
            <LibraryImportPanel source={xboxSource} onDone={onClose} />
          )}

          {tab === 'manual' && (<>
          {/* Search or selected game */}
          {!selected ? (
            <div>
              <input
                type="search"
                value={query}
                onChange={e => setQuery(e.target.value)}
                autoFocus
                placeholder="Rechercher un jeu dans le catalogue…"
                className="w-full rounded-[8px] border border-border bg-input-bg px-4 py-2.5 text-[13px] text-primary outline-none placeholder:text-faint transition-colors focus:border-accent/40"
              />
              {searchEnabled && (
                <div className="mt-2 max-h-[280px] overflow-y-auto rounded-[10px] border border-border bg-panel">
                  {isFetching && (
                    <div className="px-4 py-3 text-[12px] text-muted">Recherche…</div>
                  )}
                  {!isFetching && searchData && searchData.items.length === 0 && (
                    <div className="px-4 py-3 text-[12px] text-muted">
                      Aucun jeu trouvé pour « {debouncedQuery} ».
                    </div>
                  )}
                  {!isFetching && searchData && searchData.items.map(g => (
                    <button
                      key={g.id}
                      type="button"
                      onClick={() => setSelected(g)}
                      className="flex w-full items-center gap-3 border-b border-border/60 px-3 py-2.5 text-left transition-colors last:border-b-0 hover:bg-hover"
                    >
                      <div
                        className="h-[44px] w-[34px] flex-shrink-0 overflow-hidden rounded-[5px]"
                        style={{ background: g.cover_url ? undefined : coverGradient(g.id) }}
                      >
                        {g.cover_url && <img src={g.cover_url} alt="" className="h-full w-full object-cover" />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13px] font-medium text-primary">{g.title}</p>
                        <p className="truncate text-[11px] text-faint">
                          {[g.genres[0]?.name, g.platforms.map(p => p.name).join(', ')].filter(Boolean).join(' · ') || '—'}
                        </p>
                      </div>
                    </button>
                  ))}
                </div>
              )}
              {!searchEnabled && debouncedQuery.length === 0 && (
                <p className="mt-2 text-[11px] text-faint">
                  Tape au moins 2 caractères pour rechercher dans le catalogue.
                </p>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-3 rounded-[10px] border border-accent/30 bg-accent-dim px-3 py-3">
              <div
                className="h-[60px] w-[46px] flex-shrink-0 overflow-hidden rounded-[5px]"
                style={{ background: selected.cover_url ? undefined : coverGradient(selected.id) }}
              >
                {selected.cover_url && <img src={selected.cover_url} alt="" className="h-full w-full object-cover" />}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[14px] font-semibold text-primary">{selected.title}</p>
                <p className="truncate text-[11px] text-muted">
                  {[selected.genres[0]?.name, selected.platforms.map(p => p.name).join(', ')].filter(Boolean).join(' · ') || '—'}
                </p>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="rounded-[6px] px-2 py-1 text-[11px] text-accent-soft transition-colors hover:bg-hover"
              >
                Changer
              </button>
            </div>
          )}

          {/* Optional fields — visible after selection */}
          {selected && (
            <div className="mt-5 flex flex-col gap-5">

              {/* Statut */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label className="text-[11px] font-semibold uppercase tracking-[0.5px] text-muted">Statut</label>
                  <span className="text-[10px] text-faint">optionnel</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {STATUS_OPTIONS.map(opt => {
                    const active = status === opt.value
                    return (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => setStatus(active ? null : opt.value)}
                        className={[
                          'rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.3px] transition-all',
                          active
                            ? opt.activeClass
                            : 'border-border text-muted hover:border-faint hover:text-primary',
                        ].join(' ')}
                      >
                        {opt.label}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Note */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label className="text-[11px] font-semibold uppercase tracking-[0.5px] text-muted">
                    Note {rating !== null && <span className="ml-1 normal-case tracking-normal text-accent-soft">{rating}/10</span>}
                  </label>
                  <span className="text-[10px] text-faint">optionnel</span>
                </div>
                <div className="flex gap-1">
                  {Array.from({ length: 10 }, (_, i) => i + 1).map(n => {
                    const active = rating !== null && rating >= n
                    return (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setRating(rating === n ? null : n)}
                        className={[
                          'h-9 flex-1 rounded-[6px] text-[12px] font-medium transition-all',
                          active
                            ? 'bg-accent text-white'
                            : 'border border-border text-muted hover:bg-hover hover:text-primary',
                        ].join(' ')}
                        aria-label={`Note ${n} sur 10`}
                      >
                        {n}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Heures jouées */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label className="text-[11px] font-semibold uppercase tracking-[0.5px] text-muted">Heures jouées</label>
                  <span className="text-[10px] text-faint">optionnel</span>
                </div>
                <div className="relative w-[140px]">
                  <input
                    type="number"
                    min={0}
                    step={0.5}
                    value={hours}
                    onChange={e => setHours(e.target.value)}
                    placeholder="0"
                    className="w-full rounded-[8px] border border-border bg-input-bg px-3 py-2 pr-10 text-[13px] text-primary outline-none placeholder:text-faint focus:border-accent/40"
                  />
                  <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-[12px] text-faint">h</span>
                </div>
              </div>

              {/* Avis */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label className="text-[11px] font-semibold uppercase tracking-[0.5px] text-muted">Avis personnel</label>
                  <span className="text-[10px] text-faint">optionnel</span>
                </div>
                <textarea
                  value={review}
                  onChange={e => setReview(e.target.value)}
                  rows={3}
                  placeholder="Tes impressions sur ce jeu…"
                  className="w-full resize-none rounded-[8px] border border-border bg-input-bg px-3 py-2 text-[13px] text-primary outline-none placeholder:text-faint focus:border-accent/40"
                />
              </div>
            </div>
          )}
          </>)}
        </div>

        {/* Erreur (mode manuel uniquement) */}
        {tab === 'manual' && addMutation.isError && (
          <div className="border-t border-danger/25 bg-danger-dim px-6 py-2.5 text-[12px] text-[#FF6B84]">
            {errorMessage(addMutation.error)}
          </div>
        )}

        {/* Footer */}
        <div className="flex justify-end gap-2 border-t border-border px-6 py-4">
          <button
            onClick={onClose}
            className="rounded-[8px] border border-border px-4 py-2 text-[13px] text-muted transition-colors hover:bg-hover hover:text-primary"
          >
            Annuler
          </button>
          {tab === 'manual' && (
            <button
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="rounded-[8px] bg-accent px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {addMutation.isPending ? 'Ajout…' : 'Ajouter à ma bibliothèque'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
