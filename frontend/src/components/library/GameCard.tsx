import StatusBadge from '@/components/library/StatusBadge'
import type { UserGameRead } from '@/types/userGame'

type MenuHandler = (e: React.MouseEvent, userGame: UserGameRead) => void

function formatHours(h: number): string {
  if (h < 1) return '< 1h'
  return `${Math.round(h)}h`
}

function scoreColor(score: number): string {
  if (score >= 75) return '#5DE89E'
  if (score >= 50) return '#F5C842'
  return '#FF6B84'
}

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
  userGame: UserGameRead
  detailed: boolean
  onMenu: MenuHandler
}

export default function GameCard({ userGame, detailed, onMenu }: Props) {
  const { game } = userGame
  const genre = game.genres[0]?.name ?? ''
  const platform = game.steam_id != null ? 'PC' : (game.platforms[0]?.name ?? '')
  const releaseYear = game.release_date ? new Date(game.release_date).getFullYear() : null

  const scores: { label: string; value: number }[] = [
    game.igdb_rating !== null ? { label: 'IGDB', value: Math.round(game.igdb_rating) } : null,
    game.metacritic_score !== null ? { label: 'MC', value: game.metacritic_score } : null,
    game.opencritic_score !== null ? { label: 'OC', value: game.opencritic_score } : null,
    game.steam_score !== null ? { label: 'Steam', value: game.steam_score } : null,
  ].filter((s): s is { label: string; value: number } => s !== null)

  const coverW = detailed ? 52 : 44
  const coverH = detailed ? 68 : 56

  return (
    <div
      className="group relative flex cursor-pointer gap-3 rounded-[8px] border border-transparent px-3 py-3 transition-all hover:border-border hover:bg-hover"
      onContextMenu={e => { e.preventDefault(); onMenu(e, userGame) }}
    >
      {/* Kebab button */}
      <button
        type="button"
        onClick={e => { e.stopPropagation(); onMenu(e, userGame) }}
        className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-[4px] border border-border bg-panel text-[13px] leading-none text-muted opacity-0 transition-opacity hover:border-faint hover:bg-hover hover:text-primary group-hover:opacity-100"
        aria-label="Options"
      >
        ⋮
      </button>

      {/* Cover */}
      <div
        style={{
          width: coverW,
          height: coverH,
          borderRadius: 6,
          flexShrink: 0,
          overflow: 'hidden',
          background: game.cover_url ? undefined : coverGradient(game.id),
          position: 'relative',
        }}
      >
        {game.cover_url ? (
          <img src={game.cover_url} alt={game.title} className="h-full w-full object-cover" />
        ) : (
          <>
            <div className="absolute inset-0" style={{ background: 'linear-gradient(to bottom, transparent 40%, rgba(0,0,0,0.6))' }} />
            <span className="absolute bottom-1 left-0 right-0 z-10 px-1 text-center text-[6px] font-bold uppercase leading-tight tracking-wide text-white/80">
              {game.title.slice(0, 14)}
            </span>
          </>
        )}
      </div>

      {/* Info */}
      <div className="flex min-w-0 flex-1 flex-col justify-center gap-1">
        <p className="truncate text-[13px] font-medium text-primary">{game.title}</p>

        {(genre || platform || releaseYear) && (
          <p className="truncate text-[12px] text-faint">
            {[genre, platform, releaseYear ? String(releaseYear) : ''].filter(Boolean).join(' · ')}
          </p>
        )}

        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-1.5 overflow-hidden">
            {userGame.status && <StatusBadge status={userGame.status} />}
            {userGame.hours_played !== null && userGame.hours_played > 0 && (
              <span className="whitespace-nowrap text-[12px] text-faint">
                · {formatHours(userGame.hours_played)}
              </span>
            )}
          </div>
          {!detailed && userGame.user_rating !== null && (
            <span className="ml-auto whitespace-nowrap text-[12px] font-semibold text-[#F5C842]">
              {userGame.user_rating}<span className="text-[10px] font-normal text-faint">/10</span>
            </span>
          )}
        </div>

        {/* Rating bar (detailed) */}
        {detailed && userGame.user_rating !== null && (
          <div className="flex items-center gap-2">
            <div className="h-[3px] flex-1 overflow-hidden rounded-full bg-hover">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${(userGame.user_rating / 10) * 100}%`,
                  background: 'linear-gradient(to right, #1035C0, #F5C842)',
                }}
              />
            </div>
            <span className="text-[12px] font-bold text-[#F5C842]">{userGame.user_rating}</span>
          </div>
        )}

        {/* Metadata (detailed) */}
        {detailed && (userGame.completed_at || game.hltb_main !== null) && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
            {userGame.completed_at && (
              <span className="whitespace-nowrap text-[10px] text-faint">
                ✓ {new Date(userGame.completed_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })}
              </span>
            )}
            {game.hltb_main !== null && (
              <span className="whitespace-nowrap text-[10px] text-faint">
                HLTB ~{Math.round(game.hltb_main)}h
              </span>
            )}
          </div>
        )}

        {/* Critic scores (detailed) */}
        {detailed && scores.length > 0 && (
          <div className="flex flex-wrap items-center gap-1">
            {scores.map(s => (
              <span
                key={s.label}
                className="rounded px-1.5 py-0.5 text-[10px] font-semibold"
                style={{
                  color: scoreColor(s.value),
                  background: `${scoreColor(s.value)}18`,
                  border: `1px solid ${scoreColor(s.value)}30`,
                }}
              >
                {s.label} {s.value}
              </span>
            ))}
          </div>
        )}

        {/* Review (detailed) */}
        {detailed && userGame.review && (
          <p
            className="mt-0.5 border-t border-border pt-2 text-[11px] italic leading-relaxed text-muted"
            style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
          >
            {userGame.review}
          </p>
        )}
      </div>
    </div>
  )
}
