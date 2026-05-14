import { pickStoreLink, STORE_LABEL } from '@/lib/storeLinks'
import type { CitedGame, StorePlatform } from '@/types/store'

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
  game: CitedGame
  preferredPlatform?: StorePlatform | null
}

export default function GameInlineCard({ game, preferredPlatform }: Props) {
  const link = pickStoreLink(game.store_links, preferredPlatform)

  return (
    <div style={{
      borderRadius: 8,
      border: '1px solid #2E2E2E',
      overflow: 'hidden',
      background: '#141414',
      display: 'flex',
      flexDirection: 'column',
    }}>
      <div style={{
        width: '100%',
        aspectRatio: '3/4',
        background: game.cover_url ? undefined : coverGradient(game.id),
        overflow: 'hidden',
        flexShrink: 0,
      }}>
        {game.cover_url && (
          <img
            src={game.cover_url}
            alt={game.title}
            style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
            loading="lazy"
            onError={e => {
              const img = e.currentTarget
              img.style.display = 'none'
              if (img.parentElement) {
                img.parentElement.style.background = coverGradient(game.id)
              }
            }}
          />
        )}
      </div>

      <div style={{ padding: '8px 10px', flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <p style={{
          margin: 0,
          fontSize: 12,
          fontFamily: 'Orbitron, sans-serif',
          fontWeight: 600,
          color: '#EBEBEB',
          lineHeight: 1.3,
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}>
          {game.title}
        </p>

        {link ? (
          <a
            href={link.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'inline-block',
              marginTop: 'auto',
              fontSize: 12,
              color: '#5B7EFF',
              textDecoration: 'none',
              fontWeight: 500,
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = '#7B9EFF' }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = '#5B7EFF' }}
          >
            {STORE_LABEL[link.platform]} ↗
          </a>
        ) : (
          <span style={{ fontSize: 12, color: '#555555', marginTop: 'auto' }}>
            Aucun lien store
          </span>
        )}
      </div>
    </div>
  )
}
