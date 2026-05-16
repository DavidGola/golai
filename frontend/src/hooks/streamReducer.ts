/**
 * streamReducer — Pure function mapping SSE events to UIMessage updates.
 *
 * Aucune dépendance React/DOM : 100% testable en isolation. Le hook qui le
 * consomme appelle `setMessages(prev => prev.map(m => m.id === id ? reduceMessage(m, event) : m))`.
 *
 * Tout event SSE non géré (ex: anonymous chat reçoit moins d'events que auth)
 * retourne le message inchangé — le reducer est tolérant aux events qu'il
 * ne connaît pas, ce qui permet de partager le reducer entre les deux hooks.
 */

import type { SseEvent } from '@/lib/sseClient'
import type { ProposalActionType } from '@/types/proposal'
import type { DebugEvent, UIMessage, UIProposal } from '@/hooks/useChatStream'

interface ReduceContext {
  /** Pour les events token : si un tool a déjà été appelé, on reset le content
   *  accumulé (on n'affiche que le texte post-tool). Géré par le hook. */
  toolSeen: boolean
  /** Content accumulé indépendamment du state React, pour le passer au reveal
   *  animation. Géré par le hook. */
  contentAcc: string
}

function sseToUIProposal(data: { proposal_id: string; action_type: string; [k: string]: unknown }): UIProposal {
  const { proposal_id, action_type, ...rest } = data
  return {
    id: proposal_id,
    action_type: action_type as ProposalActionType,
    payload: rest as Record<string, unknown>,
    state: 'pending',
  }
}

/**
 * Applique un event SSE à un UIMessage. Pure function.
 *
 * - Pour les events qui touchent à l'animation (`done`) ou à l'identité du
 *   message (`done` swap l'id temp → vrai id DB), le reducer fait la mutation
 *   d'état brute mais ne lance pas d'effet (animation reveal, query invalidation) :
 *   ces effets restent dans le hook React qui orchestre.
 * - `cited_games`, `proposal` : events que l'anonymous ne reçoit pas, retournés
 *   inchangés sans erreur.
 */
export function reduceMessage(
  msg: UIMessage,
  event: SseEvent,
  ctx: ReduceContext,
): UIMessage {
  switch (event.type) {
    case 'token':
      // Si un tool a été appelé, on remplace le content (texte post-tool).
      // Sinon on accumule.
      return ctx.toolSeen
        ? { ...msg, content: ctx.contentAcc, currentTool: null }
        : { ...msg, content: ctx.contentAcc }

    case 'tool':
      return { ...msg, currentTool: event.name, content: '' }

    case 'tool_call': {
      const dbg: DebugEvent = {
        kind: 'tool_call',
        ts: Date.now(),
        name: event.data.name,
        args_preview: event.data.args_preview,
        tool_call_id: event.data.tool_call_id,
      }
      return { ...msg, debugEvents: [...(msg.debugEvents ?? []), dbg] }
    }

    case 'tool_result': {
      const dbg: DebugEvent = {
        kind: 'tool_result',
        ts: Date.now(),
        name: event.data.name,
        duration_ms: event.data.duration_ms,
        result_preview: event.data.result_preview,
        result_json: event.data.result_json ?? event.data.result_preview,
        tool_call_id: event.data.tool_call_id,
      }
      return { ...msg, debugEvents: [...(msg.debugEvents ?? []), dbg] }
    }

    case 'proposal': {
      const incoming = sseToUIProposal(event.data)
      const dbg: DebugEvent = {
        kind: 'proposal',
        ts: Date.now(),
        proposal_id: event.data.proposal_id,
        action_type: event.data.action_type,
      }
      return {
        ...msg,
        proposals: [...(msg.proposals ?? []), incoming],
        debugEvents: [...(msg.debugEvents ?? []), dbg],
      }
    }

    case 'cited_games':
      return { ...msg, citedGames: event.games }

    case 'done':
      // ID swap : tmp-ai-xxx → vraie id DB. animatingChars = 0 pour démarrer
      // l'animation typewriter (orchestrée par le hook).
      return { ...msg, id: event.assistantMessageId, currentTool: null, animatingChars: 0 }

    case 'error':
      return { ...msg, content: `Erreur : ${event.message}`, isStreaming: false, currentTool: null }
  }
}
