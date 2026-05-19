import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import GameInlineCard from '@/components/chat/GameInlineCard'
import type { CitedGame } from '@/types/store'

interface Props {
  content: string
  citedGames: CitedGame[]
}

interface Segment {
  text: string
  game: CitedGame | null
}

function buildSegments(content: string, citedGames: CitedGame[]): Segment[] {
  const paragraphs = content.split(/\n\n+/)
  const usedIds = new Set<string>()

  return paragraphs
    .filter(p => p.trim())
    .map(para => {
      const lower = para.toLowerCase()
      const game = citedGames.find(
        g => !usedIds.has(g.id) && lower.includes(g.title.toLowerCase()),
      ) ?? null
      if (game) usedIds.add(game.id)
      return { text: para, game }
    })
}

export default function CitedGamesRenderer({ content, citedGames }: Props) {
  const segments = buildSegments(content, citedGames)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {segments.map((seg, i) => (
        <div
          key={i}
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          {seg.game && (
            <div style={{ width: 90 }}>
              <GameInlineCard game={seg.game} />
            </div>
          )}
          <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{seg.text}</ReactMarkdown>
          </div>
        </div>
      ))}
    </div>
  )
}
