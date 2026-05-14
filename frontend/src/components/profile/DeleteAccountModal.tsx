import { useState } from 'react'
import axios from 'axios'

interface Props {
  open: boolean
  onConfirm: (password: string) => Promise<void>
  onCancel: () => void
}

export default function DeleteAccountModal({ open, onConfirm, onCancel }: Props) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  if (!open) return null

  function handleClose() {
    setPassword('')
    setError(null)
    onCancel()
  }

  async function handleSubmit() {
    setError(null)
    setLoading(true)
    try {
      await onConfirm(password)
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.status === 403) {
        setError('Mot de passe incorrect.')
      } else {
        setError('Une erreur est survenue. Réessaie.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onMouseDown={e => { if (e.target === e.currentTarget) handleClose() }}
    >
      <div className="w-full max-w-[400px] rounded-[16px] border border-border bg-elevated p-6 shadow-2xl">
        <h2 className="mb-2 text-[16px] font-semibold text-primary">Supprimer ton compte</h2>
        <p className="mb-4 text-[13px] text-muted">
          Cette action est irréversible. Toutes tes conversations et données seront supprimées définitivement.
        </p>
        <label className="mb-1 block text-[12px] font-medium text-muted">
          Confirme avec ton mot de passe
        </label>
        <input
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && password) handleSubmit() }}
          className="mb-1 w-full rounded-[8px] border border-border bg-surface px-3 py-2 text-[14px] text-primary outline-none focus:border-accent"
          placeholder="Mot de passe"
          disabled={loading}
        />
        {error && (
          <p className="mb-3 text-[12px] text-danger">{error}</p>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={handleClose}
            disabled={loading}
            className="rounded-[8px] border border-border px-4 py-2 text-[13px] text-muted transition-colors hover:bg-hover hover:text-primary disabled:opacity-50"
          >
            Annuler
          </button>
          <button
            onClick={handleSubmit}
            disabled={!password || loading}
            className="rounded-[8px] border border-danger/30 bg-danger-dim px-4 py-2 text-[13px] font-medium text-danger transition-colors hover:bg-danger/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? 'Suppression…' : 'Supprimer mon compte'}
          </button>
        </div>
      </div>
    </div>
  )
}
