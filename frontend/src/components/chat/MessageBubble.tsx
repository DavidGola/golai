import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { UIMessage } from '@/hooks/useChatStream'
import ProposalCard from '@/components/chat/ProposalCard'
import DebugPanel from '@/components/chat/DebugPanel'
import CitedGamesRenderer from '@/components/chat/CitedGamesRenderer'

function toolLabel(toolName: string): string {
  if (toolName === 'search_games' || toolName === 'search_games_anon') {
    return 'Recherche de jeux pertinents…'
  }
  if (toolName === 'get_my_library') return 'Lecture de ta bibliothèque…'
  if (toolName === 'propose_add_to_library') return 'Préparation de la proposition…'
  if (toolName === 'propose_change_status') return 'Préparation de la proposition…'
  if (toolName === 'propose_set_rating') return 'Préparation de la proposition…'
  if (toolName === 'propose_remove_from_library') return 'Préparation de la proposition…'
  return `Exécution de ${toolName}…`
}

export default function MessageBubble({ message }: { message: UIMessage }) {
  const isUser = message.role === 'user'

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      padding: '6px 24px',
      maxWidth: 680, width: '100%', margin: '0 auto',
      alignItems: isUser ? 'flex-end' : 'flex-start',
    }}>

      <div style={{
        maxWidth: isUser ? '72%' : '86%',
        borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
        border: isUser ? '1px solid var(--color-accent-shine)' : '1px solid var(--color-separator)',
        background: isUser ? 'var(--color-user-bubble)' : 'var(--color-elevated)',
        color: 'var(--color-content)',
        padding: '12px 16px',
        fontSize: 14, lineHeight: 1.6,
        boxShadow: isUser ? '0 0 16px var(--color-accent-dim)' : undefined,
      }}>
        {isUser ? (
          <span style={{ whiteSpace: 'pre-wrap' }}>{message.content}</span>
        ) : message.currentTool ? (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            color: 'var(--color-subtle)', fontStyle: 'italic',
          }}>
            <span style={{
              display: 'inline-block', width: 8, height: 8,
              borderRadius: '50%', background: 'var(--color-accent-soft)',
              animation: 'blink 0.9s step-end infinite',
            }} />
            {toolLabel(message.currentTool)}
          </div>
        ) : message.isStreaming && message.animatingChars == null ? (
          <span style={{ color: '#555555', fontStyle: 'italic', fontSize: 13 }}>
            Génération en cours…
          </span>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none">
            {message.animatingChars != null ? (
              <>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content.slice(0, message.animatingChars)}
                </ReactMarkdown>
                <span
                  style={{
                    display: 'inline-block', width: 2, height: 14,
                    background: 'var(--color-accent-soft)', borderRadius: 1,
                    marginLeft: 2, verticalAlign: 'bottom', transform: 'translateY(2px)',
                    animation: 'blink 0.9s step-end infinite',
                  }}
                />
              </>
            ) : message.citedGames && message.citedGames.length > 0 ? (
              <CitedGamesRenderer
                content={message.content}
                citedGames={message.citedGames}
              />
            ) : (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            )}
            {message.animatingChars == null && message.proposals?.map(proposal => (
              <ProposalCard key={proposal.id} proposal={proposal} />
            ))}
            {message.animatingChars == null && <DebugPanel events={message.debugEvents ?? []} />}
          </div>
        )}
      </div>
    </div>
  )
}
