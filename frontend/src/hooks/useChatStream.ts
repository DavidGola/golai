import { useState, useRef, useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { streamMessage } from '@/lib/sseClient'
import { animateMessageReveal } from '@/hooks/animateReveal'
import { reduceMessage } from '@/hooks/streamReducer'
import type { ChatIntent } from '@/lib/chatIntents'
import type { MessageRead } from '@/types/conversation'
import type { ProposalActionType, ProposalState } from '@/types/proposal'
import type { CitedGame } from '@/types/store'

export interface UIProposal {
  id: string
  action_type: ProposalActionType
  payload: Record<string, unknown>
  state: ProposalState
}

export type DebugEvent =
  | { kind: 'tool_call'; ts: number; name: string; args_preview: string; tool_call_id: string }
  | { kind: 'tool_result'; ts: number; name: string; duration_ms: number | null; result_preview: string; result_json: string; tool_call_id: string }
  | { kind: 'proposal'; ts: number; proposal_id: string; action_type: string }

export interface UIMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
  currentTool?: string | null
  animatingChars?: number | null
  proposals?: UIProposal[]
  debugEvents?: DebugEvent[]
  citedGames?: CitedGame[]
}

function toUIMessage(m: MessageRead, debugEvents?: Map<string, DebugEvent[]>): UIMessage {
  return {
    id: m.id,
    role: m.role as 'user' | 'assistant',
    content: m.content,
    proposals: m.proposals?.length
      ? m.proposals.map(p => ({
          id: p.id,
          action_type: p.action_type,
          payload: p.payload as Record<string, unknown>,
          state: p.state,
        }))
      : undefined,
    citedGames: m.cited_games ?? undefined,
    debugEvents: debugEvents?.get(m.id),
  }
}

export function useChatStream(conversationId: string, initialMessages: MessageRead[]) {
  // debugEvents survit au reset post-streaming (frontend-only, absent du serveur)
  const debugEventsRef = useRef<Map<string, DebugEvent[]>>(new Map())

  const [messages, setMessages] = useState<UIMessage[]>(() =>
    initialMessages.map(m => toUIMessage(m)),
  )
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const qc = useQueryClient()

  useEffect(() => {
    if (isStreaming) return
    setMessages(initialMessages.map(m => toUIMessage(m, debugEventsRef.current)))
  }, [conversationId, initialMessages, isStreaming])

  async function send(content: string, intent?: ChatIntent) {
    if (isStreaming) return

    const userMsg: UIMessage = { id: `tmp-user-${Date.now()}`, role: 'user', content }
    const assistantMsg: UIMessage = { id: `tmp-ai-${Date.now()}`, role: 'assistant', content: '', isStreaming: true }

    setMessages(prev => [...prev, userMsg, assistantMsg])
    setIsStreaming(true)

    const ac = new AbortController()
    abortRef.current = ac
    let toolSeen = false
    let contentAcc = ''
    let assistantId = assistantMsg.id  // mutera après 'done' (swap vers id DB)

    try {
      for await (const event of streamMessage(conversationId, content, intent)) {
        if (ac.signal.aborted) break

        // Maintenir l'état "out of React" pour le reducer (toolSeen, contentAcc).
        // Le reducer reste pur ; le hook orchestre les transitions.
        if (event.type === 'token') {
          contentAcc += event.data
        } else if (event.type === 'tool') {
          toolSeen = true
          contentAcc = ''
        }

        setMessages(prev =>
          prev.map(m =>
            m.id === assistantId ? reduceMessage(m, event, { toolSeen, contentAcc }) : m,
          ),
        )

        if (event.type === 'done') {
          const finalContent = contentAcc
          const newId = event.assistantMessageId

          // Persiste les debugEvents accumulés sur la nouvelle id DB
          setMessages(prev => {
            const target = prev.find(m => m.id === newId)
            if (target?.debugEvents?.length) {
              debugEventsRef.current.set(newId, target.debugEvents)
            }
            return prev
          })

          assistantId = newId
          await animateMessageReveal(setMessages, newId, finalContent, ac.signal)

          if (!ac.signal.aborted) {
            await qc.invalidateQueries({ queryKey: ['conversations', conversationId] })
            await qc.invalidateQueries({ queryKey: ['conversations'] })
          }
        }
      }
    } catch (err) {
      console.error('[useChatStream] SSE stream error:', err)
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantId
            ? { ...m, content: 'Une erreur est survenue.', isStreaming: false }
            : m,
        ),
      )
    } finally {
      setIsStreaming(false)
    }
  }

  useEffect(() => {
    return () => { abortRef.current?.abort() }
  }, [])

  return { messages, send, isStreaming }
}
