import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { confirmProposal, cancelProposal } from '@/api/proposals'
import type { UIProposal } from '@/hooks/useChatStream'

function statusLabel(status: string | null | undefined): string {
  switch (status) {
    case 'completed': return 'Terminé'
    case 'todo': return 'À faire'
    case 'dropped': return 'Abandonné'
    case 'not_started': return 'Pas commencé'
    default: return status ?? '—'
  }
}

function actionTitle(proposal: UIProposal): string {
  const p = proposal.payload
  const title = String(p.title ?? '')
  switch (proposal.action_type) {
    case 'add_to_library': {
      const status = p.status ? ` en « ${statusLabel(String(p.status))} »` : ''
      const extras: string[] = []
      if (p.rating != null) extras.push(`note ${p.rating}/10`)
      if (p.review) extras.push('avec avis')
      const tail = extras.length > 0 ? ` — ${extras.join(' + ')}` : ''
      return `Ajouter ${title}${status}${tail}`
    }
    case 'change_status': {
      const from = p.current && typeof p.current === 'object' && 'status' in p.current
        ? statusLabel(String((p.current as Record<string, unknown>).status))
        : '?'
      const to = p.target && typeof p.target === 'object' && 'status' in p.target
        ? statusLabel(String((p.target as Record<string, unknown>).status))
        : '?'
      return `${title} : passer de « ${from} » à « ${to} »`
    }
    case 'set_rating': {
      const parts: string[] = []
      if (p.rating != null) parts.push(`note ${p.rating}/10`)
      if (p.review) parts.push('review')
      return `${title} — ${parts.join(' + ')}`
    }
    case 'remove_from_library':
      return `Supprimer ${title} de la bibliothèque`
    default:
      return title
  }
}

const ACTION_ICONS: Record<string, string> = {
  add_to_library: '+',
  change_status: '↻',
  set_rating: '★',
  remove_from_library: '✕',
}

export default function ProposalCard({
  proposal,
  onStateChange,
}: {
  proposal: UIProposal
  onStateChange?: (updated: UIProposal) => void
}) {
  const [state, setState] = useState(proposal.state)
  const [loading, setLoading] = useState(false)
  const qc = useQueryClient()

  const isDelete = proposal.action_type === 'remove_from_library'
  const coverUrl = String(proposal.payload.cover_url ?? '')
  const icon = ACTION_ICONS[proposal.action_type] ?? '?'

  async function handleConfirm() {
    if (state !== 'pending' || loading) return
    setLoading(true)
    try {
      await confirmProposal(proposal.id)
      setState('confirmed')
      onStateChange?.({ ...proposal, state: 'confirmed' })
      await qc.invalidateQueries({ queryKey: ['user-games'] })
    } catch {
      // keep pending, user can retry
    } finally {
      setLoading(false)
    }
  }

  async function handleCancel() {
    if (state !== 'pending' || loading) return
    setLoading(true)
    try {
      await cancelProposal(proposal.id)
      setState('cancelled')
      onStateChange?.({ ...proposal, state: 'cancelled' })
    } catch {
      // keep pending
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      marginTop: 10,
      border: '1px solid var(--color-separator)',
      borderRadius: 10,
      background: '#141414',
      overflow: 'hidden',
      display: 'flex',
      alignItems: 'stretch',
      maxWidth: 440,
      opacity: state === 'pending' ? 1 : 0.65,
    }}>
      {coverUrl && (
        <div style={{ width: 56, flexShrink: 0 }}>
          <img
            src={coverUrl}
            alt=""
            style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
          />
        </div>
      )}

      <div style={{ flex: 1, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            fontSize: 13, lineHeight: 1,
            color: isDelete ? '#FF5A5A' : 'var(--color-accent-soft)',
            fontWeight: 700,
          }}>
            {icon}
          </span>
          <span style={{ fontSize: 13, color: '#D0D0D0', lineHeight: 1.4 }}>
            {actionTitle(proposal)}
          </span>
        </div>

        {state === 'pending' && (
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              onClick={handleConfirm}
              disabled={loading}
              style={{
                padding: '4px 12px',
                borderRadius: 6,
                border: 'none',
                background: isDelete ? '#7A1A1A' : '#1A3A7A',
                color: 'var(--color-content)',
                fontSize: 12,
                fontWeight: 600,
                cursor: loading ? 'default' : 'pointer',
                opacity: loading ? 0.6 : 1,
              }}
            >
              Confirmer
            </button>
            <button
              onClick={handleCancel}
              disabled={loading}
              style={{
                padding: '4px 12px',
                borderRadius: 6,
                border: '1px solid #3A3A3A',
                background: 'transparent',
                color: '#888',
                fontSize: 12,
                fontWeight: 600,
                cursor: loading ? 'default' : 'pointer',
                opacity: loading ? 0.6 : 1,
              }}
            >
              Annuler
            </button>
          </div>
        )}

        {state === 'confirmed' && (
          <span style={{ fontSize: 12, color: '#4CAF50', fontWeight: 600 }}>
            ✓ Confirmé
          </span>
        )}

        {state === 'cancelled' && (
          <span style={{ fontSize: 12, color: '#888', fontWeight: 600 }}>
            Annulé
          </span>
        )}
      </div>
    </div>
  )
}
