/**
 * animateReveal — Animation typewriter du message final.
 *
 * Extraite de useChatStream pour isoler le mécanisme d'animation de la
 * logique de streaming SSE. Durée cible ~2s quelle que soit la longueur
 * du message ; respecte un signal d'annulation.
 */

import type { Dispatch, SetStateAction } from 'react'
import type { UIMessage } from '@/hooks/useChatStream'

const TICK_MS = 25
const TARGET_DURATION_MS = 2000

/**
 * Révèle progressivement `content` char-by-char en mettant à jour
 * `animatingChars` sur le message d'id `messageId`. À la fin, set
 * `isStreaming: false` et `animatingChars: null` (= reveal terminé).
 *
 * Si `signal.aborted` à n'importe quel moment, arrête sans toucher au
 * state final (le hook gérera le cleanup).
 */
export async function animateMessageReveal(
  setMessages: Dispatch<SetStateAction<UIMessage[]>>,
  messageId: string,
  content: string,
  signal: AbortSignal,
): Promise<void> {
  const totalTicks = TARGET_DURATION_MS / TICK_MS
  const charsPerTick = Math.max(1, Math.ceil(content.length / totalTicks))

  for (let i = charsPerTick; i <= content.length; i += charsPerTick) {
    if (signal.aborted) return
    await new Promise<void>(r => setTimeout(r, TICK_MS))
    if (signal.aborted) return
    const revealed = Math.min(i, content.length)
    setMessages(prev =>
      prev.map(m => (m.id === messageId ? { ...m, animatingChars: revealed } : m)),
    )
  }

  if (signal.aborted) return
  setMessages(prev =>
    prev.map(m =>
      m.id === messageId ? { ...m, isStreaming: false, animatingChars: null } : m,
    ),
  )
}
