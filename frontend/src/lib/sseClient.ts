import { tokenStorage } from '@/lib/tokenStorage'

export type AnonymousSseEvent =
  | { type: 'token'; data: string }
  | { type: 'tool'; name: string }
  | { type: 'done'; tokensUsed: number | null }
  | { type: 'error'; message: string }

export type SseEvent =
  | { type: 'token'; data: string }
  | { type: 'tool'; name: string }
  | { type: 'done'; assistantMessageId: string; tokensUsed: number | null }
  | { type: 'error'; message: string }

export async function* streamMessage(
  conversationId: string,
  content: string,
): AsyncGenerator<SseEvent> {
  const token = tokenStorage.get()
  const baseUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

  const response = await fetch(
    `${baseUrl}/conversations/${conversationId}/messages`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ content }),
    },
  )

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''

      for (const part of parts) {
        const lines = part.trim().split('\n')
        let eventType = ''
        let eventData = ''

        for (const line of lines) {
          if (line.startsWith('event: ')) eventType = line.slice(7).trim()
          else if (line.startsWith('data: ')) eventData = line.slice(6)
        }

        if (!eventType) continue

        if (eventType === 'token') {
          const parsed = JSON.parse(eventData) as { text: string }
          yield { type: 'token', data: parsed.text }
        } else if (eventType === 'tool') {
          const parsed = JSON.parse(eventData) as { name: string }
          yield { type: 'tool', name: parsed.name }
        } else if (eventType === 'done') {
          const parsed = JSON.parse(eventData) as {
            assistant_message_id: string
            tokens_used: number | null
          }
          yield {
            type: 'done',
            assistantMessageId: parsed.assistant_message_id,
            tokensUsed: parsed.tokens_used,
          }
          return
        } else if (eventType === 'error') {
          const parsed = JSON.parse(eventData) as { message: string }
          yield { type: 'error', message: parsed.message }
          return
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

export async function* streamAnonymousMessage(
  content: string,
  history: { role: 'user' | 'assistant'; content: string }[],
): AsyncGenerator<AnonymousSseEvent> {
  const baseUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

  const response = await fetch(`${baseUrl}/chat/anonymous`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, history }),
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''

      for (const part of parts) {
        const lines = part.trim().split('\n')
        let eventType = ''
        let eventData = ''

        for (const line of lines) {
          if (line.startsWith('event: ')) eventType = line.slice(7).trim()
          else if (line.startsWith('data: ')) eventData = line.slice(6)
        }

        if (!eventType) continue

        if (eventType === 'token') {
          const parsed = JSON.parse(eventData) as { text: string }
          yield { type: 'token', data: parsed.text }
        } else if (eventType === 'tool') {
          const parsed = JSON.parse(eventData) as { name: string }
          yield { type: 'tool', name: parsed.name }
        } else if (eventType === 'done') {
          const parsed = JSON.parse(eventData) as { tokens_used: number | null }
          yield { type: 'done', tokensUsed: parsed.tokens_used }
          return
        } else if (eventType === 'error') {
          const parsed = JSON.parse(eventData) as { message: string }
          yield { type: 'error', message: parsed.message }
          return
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
