import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'
import SidebarLeft from '@/components/layout/SidebarLeft'
import MessageBubble from '@/components/chat/MessageBubble'
import ChatInput from '@/components/chat/ChatInput'
import LibraryPanel from '@/components/library/LibraryPanel'
import { useConversation, useCreateConversation } from '@/hooks/useConversations'
import { useChatStream } from '@/hooks/useChatStream'
import { useAnonymousChat } from '@/hooks/useAnonymousChat'
import { useChatConfig } from '@/hooks/useChatConfig'
import { featureFlags } from '@/lib/featureFlags'
import type { MessageRead } from '@/types/conversation'

const EMPTY_MESSAGES: MessageRead[] = []

export default function ChatPage() {
  const { user } = useAuth()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [libraryOpen, setLibraryOpen] = useState(() => {
    const saved = localStorage.getItem('golai_library_open')
    return saved === null ? true : saved === 'true'
  })
  useEffect(() => {
    localStorage.setItem('golai_library_open', String(libraryOpen))
  }, [libraryOpen])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const pendingRef = useRef<string | null>(null)

  const create = useCreateConversation()
  const { data: conv, isLoading } = useConversation(user ? id : undefined)
  const { data: chatConfig } = useChatConfig()

  // Hooks toujours appelés (Rules of Hooks) — on choisit lequel utiliser après
  const authChat = useChatStream(id ?? '', conv?.messages ?? EMPTY_MESSAGES)
  const anonChat = useAnonymousChat()
  const authSend = authChat.send

  const showAnonymousChat = !user && featureFlags.anonymousChatEnabled
  const { messages, send: activeSend, isStreaming } = user ? authChat : anonChat

  useEffect(() => {
    if (id && pendingRef.current) {
      const msg = pendingRef.current
      pendingRef.current = null
      authSend(msg)
    }
  }, [id, authSend])

  async function handleSend(content: string) {
    if (id) {
      authSend(content)
      return
    }
    pendingRef.current = content
    const newConv = await create.mutateAsync(undefined)
    navigate(`/chat/${newConv.id}`, { replace: true })
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const title = conv?.title ?? 'Nouvelle conversation'

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      {/* Sidebar — uniquement si connecté */}
      {user && <SidebarLeft />}

      {/* Chat central */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: '#111111' }}>

        {/* Header */}
        <div style={{
          height: 60, flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 20px', borderBottom: '1px solid #2E2E2E', background: '#111111',
        }}>
          {/* Logo quand pas connecté */}
          {!user && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 28, height: 28, borderRadius: 6, background: '#1035C0',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: "'Orbitron', sans-serif", fontSize: 11, fontWeight: 700, color: '#fff',
                boxShadow: '0 0 12px rgba(16,53,192,0.3)',
              }}>G</div>
              <span style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 13, fontWeight: 600, letterSpacing: '1.5px', color: '#EBEBEB' }}>
                GOLAI
              </span>
            </div>
          )}

          {/* Titre conv quand connecté */}
          {user && (
            <span style={{ fontSize: 14, fontWeight: 500, color: '#EBEBEB', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {title}
            </span>
          )}

          {/* Actions header */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {user && (
              <button
                onClick={() => setLibraryOpen(v => !v)}
                title="Bibliothèque"
                style={{
                  width: 34, height: 34, borderRadius: 6,
                  border: libraryOpen ? '1px solid rgba(16,53,192,0.3)' : '1px solid transparent',
                  background: libraryOpen ? 'rgba(16,53,192,0.12)' : 'transparent',
                  color: libraryOpen ? '#5B7EFF' : '#888888',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 14, cursor: 'pointer', transition: 'all 0.15s',
                } as React.CSSProperties}
              >
                <svg width="17" height="17" viewBox="0 0 17 17" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="2" y="2" width="13" height="13" rx="2"/>
                  <path d="M5 6h7M5 8.5h7M5 11h4"/>
                </svg>
              </button>
            )}
            {!user && (
              <div style={{ display: 'flex', gap: 8 }}>
                <Link to="/login" style={{
                  padding: '7px 14px', borderRadius: 8, fontSize: 13, fontWeight: 500,
                  color: '#888888', border: '1px solid #2E2E2E', transition: 'all 0.15s',
                }}>
                  Se connecter
                </Link>
                <Link to="/register" style={{
                  padding: '7px 14px', borderRadius: 8, fontSize: 13, fontWeight: 500,
                  color: '#fff', background: '#1035C0', boxShadow: '0 0 12px rgba(16,53,192,0.3)',
                  transition: 'all 0.15s',
                }}>
                  Créer un compte
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* Zone messages */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px 0' }}>
          {/* État vide */}
          {messages.length === 0 && !isLoading && (
            user ? (
              <div style={{ display: 'flex', height: '100%', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, textAlign: 'center', padding: '0 24px' }}>
                <div style={{
                  width: 56, height: 56, borderRadius: 14, background: '#1035C0',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontFamily: "'Orbitron', sans-serif", fontSize: 22, fontWeight: 700, color: '#fff',
                  boxShadow: '0 0 24px rgba(16,53,192,0.4)',
                }}>G</div>
                <p style={{ fontSize: 16, fontWeight: 500, color: '#EBEBEB' }}>Comment puis-je t'aider ?</p>
                <p style={{ fontSize: 13, color: '#888888' }}>Pose-moi une question sur le jeu vidéo.</p>
              </div>
            ) : (
              <div className="flex h-full flex-col items-center justify-center gap-5 px-6 text-center">
                <div
                  className="flex h-[56px] w-[56px] flex-shrink-0 items-center justify-center rounded-[14px] bg-accent font-display text-[22px] font-bold text-white"
                  style={{ boxShadow: '0 0 24px rgba(16,53,192,0.4)' }}
                >G</div>
                <div className="flex flex-col gap-1">
                  <p className="font-display text-[15px] font-semibold tracking-[2px] text-primary">GOLAI</p>
                  <p className="text-[13px] text-muted">Recommandation de jeux vidéo</p>
                </div>
                <div className="max-w-[420px] space-y-1.5">
                  <p className="text-[13px] text-primary">Décris une humeur, un jeu que tu as aimé, ou ton temps disponible.</p>
                  <p className="text-[13px] text-muted">L'agent analyse tes goûts et te recommande ce qui colle.</p>
                </div>
                <p className="text-[13px] italic text-muted">Exemple : « Quel jeu jouer ce soir si j'ai aimé Hades ? »</p>
                <Link to="/about" className="mt-2 text-[12px] text-faint transition-colors hover:text-muted">
                  À propos de GolAi
                </Link>
              </div>
            )
          )}

          {id && isLoading && (
            <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', color: '#888888', fontSize: 14 }}>
              Chargement…
            </div>
          )}

          {messages.map(msg => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        {user ? (
          <ChatInput
            onSend={handleSend}
            disabled={isStreaming || create.isPending}
            model={chatConfig?.model}
          />
        ) : showAnonymousChat ? (
          <ChatInput
            onSend={activeSend}
            disabled={isStreaming}
            model={chatConfig?.model}
          />
        ) : (
          <AnonInput />
        )}
      </main>

      {/* Panneau bibliothèque */}
      {user && libraryOpen && <LibraryPanel onClose={() => setLibraryOpen(false)} />}
    </div>
  )
}

function AnonInput() {
  return (
    <div style={{
      flexShrink: 0, borderTop: '1px solid #2E2E2E', background: '#111111',
      padding: '12px 20px 16px',
    }}>
      <div style={{ maxWidth: 820, margin: '0 auto', textAlign: 'center' }}>
        <div style={{
          border: '1px solid #2E2E2E', borderRadius: 16, padding: '14px 18px',
          color: '#444444', fontSize: 14, background: '#181818', marginBottom: 10,
        }}>
          Parle de jeu vidéo…
        </div>
        <p style={{ fontSize: 13, color: '#888888' }}>
          <Link to="/login" style={{ color: '#5B7EFF', fontWeight: 500 }}>Connecte-toi</Link>
          {' '}ou{' '}
          <Link to="/register" style={{ color: '#5B7EFF', fontWeight: 500 }}>crée un compte</Link>
          {' '}pour discuter avec GolAi.
          {' · '}
          <Link to="/about" style={{ color: '#666666' }}>À propos</Link>
        </p>
      </div>
    </div>
  )
}
