import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { UIMessage } from '@/hooks/useChatStream'

function toolLabel(toolName: string): string {
  if (toolName === 'search_games' || toolName === 'search_games_anon') {
    return 'Recherche de jeux pertinents…'
  }
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
        marginBottom: 6, paddingLeft: 2, paddingRight: 2,
        fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.8px',
        color: isUser ? '#5B7EFF' : '#444444',
      }}>
        {isUser ? 'Toi' : 'GolAi'}
      </div>

      <div style={{
        maxWidth: isUser ? '72%' : '86%',
        borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
        border: isUser ? '1px solid rgba(16,53,192,0.35)' : '1px solid #2E2E2E',
        background: isUser ? '#0D1E52' : '#1A1A1A',
        color: '#EBEBEB',
        padding: '12px 16px',
        fontSize: 14, lineHeight: 1.6,
        boxShadow: isUser ? '0 0 16px rgba(16,53,192,0.12)' : undefined,
      }}>
        {isUser ? (
          <span style={{ whiteSpace: 'pre-wrap' }}>{message.content}</span>
        ) : message.currentTool ? (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            color: '#888888', fontStyle: 'italic',
          }}>
            <span style={{
              display: 'inline-block', width: 8, height: 8,
              borderRadius: '50%', background: '#5B7EFF',
              animation: 'blink 0.9s step-end infinite',
            }} />
            {toolLabel(message.currentTool)}
          </div>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
            {message.isStreaming && (
              <span
                style={{
                  display: 'inline-block', width: 2, height: 14,
                  background: '#5B7EFF', borderRadius: 1,
                  marginLeft: 2, verticalAlign: 'bottom', transform: 'translateY(2px)',
                  animation: 'blink 0.9s step-end infinite',
                }}
              />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
