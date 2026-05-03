import { useState, useEffect } from 'react'
import { useUpdateUserGame } from '@/hooks/useUserGames'
import type { UserGameRead, UserGameStatus } from '@/types/userGame'

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

interface Props {
  open: boolean
  userGame: UserGameRead | null
  onClose: () => void
  onRequestDelete: () => void
}

export default function EditGameModal({ open, userGame, onClose, onRequestDelete }: Props) {
  const [status, setStatus] = useState<UserGameStatus | null>(null)
  const [rating, setRating] = useState<number | null>(null)
  const [hours, setHours] = useState('')
  const [review, setReview] = useState('')

  const updateMutation = useUpdateUserGame()

  useEffect(() => {
    if (open && userGame) {
      setStatus(userGame.status)
      setRating(userGame.user_rating)
      setHours(userGame.hours_played != null ? String(userGame.hours_played) : '')
      setReview(userGame.review ?? '')
      updateMutation.reset()
    }
  }, [open, userGame]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!open || !userGame) return null

  const { game } = userGame
  const meta = [game.genres[0]?.name, game.steam_id != null ? 'PC' : game.platforms[0]?.name].filter(Boolean).join(' · ')

  const handleSubmit = () => {
    const hoursNum = hours.trim() ? Number(hours) : undefined
    updateMutation.mutate(
      {
        id: userGame.id,
        ...(status != null ? { status } : {}),
        ...(rating != null ? { user_rating: rating } : {}),
        review: review.trim(),
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
        <div className="flex items-center justify-between border-b border-border px-6 pb-4 pt-5">
          <h2 className="text-[16px] font-semibold text-primary">Modifier ce jeu</h2>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-[6px] text-muted transition-colors hover:bg-hover hover:text-primary"
            aria-label="Fermer"
          >
            ✕
          </button>
        </div>

        {/* Jeu (lecture seule) */}
        <div className="flex items-center gap-3 border-b border-border bg-panel px-6 py-3.5">
          <div
            className="h-[52px] w-[40px] flex-shrink-0 overflow-hidden rounded-[6px]"
            style={{ background: game.cover_url ? undefined : coverGradient(game.id) }}
          >
            {game.cover_url && <img src={game.cover_url} alt={game.title} className="h-full w-full object-cover" />}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-semibold text-primary">{game.title}</p>
            {meta && <p className="mt-0.5 truncate text-[11px] text-muted">{meta}</p>}
          </div>
          <span className="flex-shrink-0 rounded-[4px] border border-border bg-[rgba(255,255,255,0.04)] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.4px] text-faint">
            lecture seule
          </span>
        </div>

        {/* Champs éditables */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <div className="flex flex-col gap-5">

            {/* Statut */}
            <div>
              <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.5px] text-muted">Statut</label>
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
                        active ? opt.activeClass : 'border-border text-muted hover:border-faint hover:text-primary',
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
              <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.5px] text-muted">
                Note {rating !== null && <span className="ml-1 normal-case tracking-normal text-accent-soft">{rating}/10</span>}
              </label>
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
                        active ? 'bg-accent text-white' : 'border border-border text-muted hover:bg-hover hover:text-primary',
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
              <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.5px] text-muted">Heures jouées</label>
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

            {/* Avis personnel */}
            <div>
              <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.5px] text-muted">Avis personnel</label>
              <textarea
                value={review}
                onChange={e => setReview(e.target.value)}
                rows={3}
                placeholder="Tes impressions sur ce jeu…"
                className="w-full resize-none rounded-[8px] border border-border bg-input-bg px-3 py-2 text-[13px] text-primary outline-none placeholder:text-faint focus:border-accent/40"
              />
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-border px-6 py-4">
          <button
            type="button"
            onClick={onRequestDelete}
            className="rounded-[8px] border border-danger/30 bg-danger-dim px-4 py-2 text-[13px] font-medium text-danger transition-colors hover:bg-danger/20"
          >
            ✕ Supprimer
          </button>
          <div className="flex gap-2">
          <button
            onClick={onClose}
            className="rounded-[8px] border border-border px-4 py-2 text-[13px] text-muted transition-colors hover:bg-hover hover:text-primary"
          >
            Annuler
          </button>
          <button
            onClick={handleSubmit}
            disabled={updateMutation.isPending}
            className="rounded-[8px] bg-accent px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {updateMutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </button>
          </div>
        </div>

      </div>
    </div>
  )
}
