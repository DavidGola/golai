import { useState, useRef, useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { streamMessage } from '@/lib/sseClient'
import type { ProposalSseData } from '@/lib/sseClient'
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

function sseToUIProposal(data: ProposalSseData): UIProposal {
  const { proposal_id, action_type, ...rest } = data
  return {
    id: proposal_id,
    action_type: action_type as ProposalActionType,
    payload: rest as Record<string, unknown>,
    state: 'pending',
  }
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

    try {
      for await (const event of streamMessage(conversationId, content, intent)) {
        if (ac.signal.aborted) break

        if (event.type === 'token') {
          contentAcc += event.data
          if (toolSeen) {
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantMsg.id ? { ...m, content: contentAcc, currentTool: null } : m,
              ),
            )
          } else {
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantMsg.id ? { ...m, content: contentAcc } : m,
              ),
            )
          }
        } else if (event.type === 'tool') {
          toolSeen = true
          contentAcc = ''
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsg.id ? { ...m, currentTool: event.name, content: '' } : m,
            ),
          )
        } else if (event.type === 'tool_call') {
          const dbg: DebugEvent = {
            kind: 'tool_call',
            ts: Date.now(),
            name: event.data.name,
            args_preview: event.data.args_preview,
            tool_call_id: event.data.tool_call_id,
          }
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsg.id
                ? { ...m, debugEvents: [...(m.debugEvents ?? []), dbg] }
                : m,
            ),
          )
        } else if (event.type === 'tool_result') {
          const dbg: DebugEvent = {
            kind: 'tool_result',
            ts: Date.now(),
            name: event.data.name,
            duration_ms: event.data.duration_ms,
            result_preview: event.data.result_preview,
            result_json: event.data.result_json ?? event.data.result_preview,
            tool_call_id: event.data.tool_call_id,
          }
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsg.id
                ? { ...m, debugEvents: [...(m.debugEvents ?? []), dbg] }
                : m,
            ),
          )
        } else if (event.type === 'proposal') {
          const incomingProposal = sseToUIProposal(event.data)
          const dbg: DebugEvent = {
            kind: 'proposal',
            ts: Date.now(),
            proposal_id: event.data.proposal_id,
            action_type: event.data.action_type,
          }
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsg.id
                ? {
                    ...m,
                    proposals: [...(m.proposals ?? []), incomingProposal],
                    debugEvents: [...(m.debugEvents ?? []), dbg],
                  }
                : m,
            ),
          )
        } else if (event.type === 'cited_games') {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsg.id ? { ...m, citedGames: event.games } : m,
            ),
          )
        } else if (event.type === 'done') {
          const finalContent = contentAcc
          setMessages(prev => {
            const updated = prev.map(m => {
              if (m.id !== assistantMsg.id) return m
              if (m.debugEvents?.length) {
                debugEventsRef.current.set(event.assistantMessageId, m.debugEvents)
              }
              return { ...m, id: event.assistantMessageId, currentTool: null, animatingChars: 0 }
            })
            return updated
          })

          // Animation typewriter : durée cible ~2s quelle que soit la longueur
          const TICK_MS = 25
          const totalTicks = 2000 / TICK_MS
          const charsPerTick = Math.max(1, Math.ceil(finalContent.length / totalTicks))
          for (let i = charsPerTick; i <= finalContent.length; i += charsPerTick) {
            if (ac.signal.aborted) break
            await new Promise<void>(r => setTimeout(r, TICK_MS))
            if (ac.signal.aborted) break
            const revealed = Math.min(i, finalContent.length)
            setMessages(prev =>
              prev.map(m =>
                m.id === event.assistantMessageId ? { ...m, animatingChars: revealed } : m,
              ),
            )
          }

          if (!ac.signal.aborted) {
            setMessages(prev =>
              prev.map(m =>
                m.id === event.assistantMessageId
                  ? { ...m, isStreaming: false, animatingChars: null }
                  : m,
              ),
            )
            await qc.invalidateQueries({ queryKey: ['conversations', conversationId] })
            await qc.invalidateQueries({ queryKey: ['conversations'] })
          }
        } else if (event.type === 'error') {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsg.id
                ? { ...m, content: `Erreur : ${event.message}`, isStreaming: false, currentTool: null }
                : m,
            ),
          )
        }
      }
    } catch (err) {
      console.error('[useChatStream] SSE stream error:', err)
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantMsg.id
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
