import { useState, useRef, useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { streamMessage } from '@/lib/sseClient'
import type { MessageRead } from '@/types/conversation'

export interface UIMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
  currentTool?: string | null
}

export function useChatStream(conversationId: string, initialMessages: MessageRead[]) {
  const [messages, setMessages] = useState<UIMessage[]>(() =>
    initialMessages.map(m => ({ id: m.id, role: m.role as 'user' | 'assistant', content: m.content })),
  )
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const qc = useQueryClient()

  useEffect(() => {
    if (isStreaming) return
    setMessages(
      initialMessages.map(m => ({ id: m.id, role: m.role as 'user' | 'assistant', content: m.content })),
    )
  }, [conversationId, initialMessages, isStreaming])

  async function send(content: string) {
    if (isStreaming) return

    const userMsg: UIMessage = { id: `tmp-user-${Date.now()}`, role: 'user', content }
    const assistantMsg: UIMessage = { id: `tmp-ai-${Date.now()}`, role: 'assistant', content: '', isStreaming: true }

    setMessages(prev => [...prev, userMsg, assistantMsg])
    setIsStreaming(true)

    const ac = new AbortController()
    abortRef.current = ac
    let toolSeen = false

    try {
      for await (const event of streamMessage(conversationId, content)) {
        if (ac.signal.aborted) break

        if (event.type === 'token') {
          if (toolSeen) {
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantMsg.id ? { ...m, content: m.content + event.data, currentTool: null } : m,
              ),
            )
          } else {
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantMsg.id ? { ...m, content: m.content + event.data } : m,
              ),
            )
          }
        } else if (event.type === 'tool') {
          toolSeen = true
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsg.id ? { ...m, currentTool: event.name } : m,
            ),
          )
        } else if (event.type === 'done') {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsg.id
                ? { ...m, id: event.assistantMessageId, isStreaming: false, currentTool: null }
                : m,
            ),
          )
          await qc.invalidateQueries({ queryKey: ['conversations', conversationId] })
          await qc.invalidateQueries({ queryKey: ['conversations'] })
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
