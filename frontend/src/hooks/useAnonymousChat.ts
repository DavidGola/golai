import { useState, useRef, useEffect } from 'react'
import { streamAnonymousMessage } from '@/lib/sseClient'
import { reduceMessage } from '@/hooks/streamReducer'
import type { UIMessage } from '@/hooks/useChatStream'

export function useAnonymousChat() {
  const [messages, setMessages] = useState<UIMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const historyRef = useRef<{ role: 'user' | 'assistant'; content: string }[]>([])

  async function send(content: string) {
    if (isStreaming) return

    const userMsg: UIMessage = { id: `tmp-user-${Date.now()}`, role: 'user', content }
    const assistantId = `tmp-ai-${Date.now()}`
    const assistantMsg: UIMessage = { id: assistantId, role: 'assistant', content: '', isStreaming: true }

    // Capture l'historique confirmé AVANT d'ajouter les nouveaux messages
    const currentHistory = messages
      .filter(m => !m.isStreaming)
      .map(m => ({ role: m.role, content: m.content }))
    historyRef.current = currentHistory

    setMessages(prev => [...prev, userMsg, assistantMsg])
    setIsStreaming(true)

    const ac = new AbortController()
    abortRef.current = ac
    const timeoutId = setTimeout(() => ac.abort(), 60_000)
    let contentAcc = ''

    try {
      for await (const event of streamAnonymousMessage(content, currentHistory, ac.signal)) {
        if (ac.signal.aborted) break

        if (event.type === 'token') {
          contentAcc += event.data
          // Anonymous : on accumule directement, pas de tool-reset (les events
          // tool n'existent pas en anonyme... sauf 'tool' qui peut arriver mais
          // on n'a pas de reset comportemental, juste affichage indicateur).
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? { ...m, content: contentAcc, currentTool: null }
                : m,
            ),
          )
        } else if (event.type === 'tool') {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? reduceMessage(m, event, { toolSeen: true, contentAcc })
                : m,
            ),
          )
        } else if (event.type === 'done') {
          // Anonymous : 'done' n'a pas d'animation typewriter ni d'assistantMessageId
          // (pas de persistance DB) — on flip juste isStreaming.
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? { ...m, isStreaming: false, currentTool: null }
                : m,
            ),
          )
        } else if (event.type === 'error') {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? reduceMessage(m, event, { toolSeen: false, contentAcc })
                : m,
            ),
          )
        }
        // Les autres events (tool_call/tool_result/proposal/cited_games) ne
        // sont jamais émis par streamAnonymousMessage — pas de branche.
      }
    } catch {
      const msg = ac.signal.aborted ? 'La réponse a pris trop de temps.' : 'Une erreur est survenue.'
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantId ? { ...m, content: msg, isStreaming: false } : m,
        ),
      )
    } finally {
      clearTimeout(timeoutId)
      setIsStreaming(false)
    }
  }

  useEffect(() => {
    return () => { abortRef.current?.abort() }
  }, [])

  return { messages, send, isStreaming }
}
