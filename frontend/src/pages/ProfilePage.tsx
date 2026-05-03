import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'
import { useConversationsList, useDeleteConversation } from '@/hooks/useConversations'
import { useUserGames } from '@/hooks/useUserGames'
import { apiClient } from '@/lib/apiClient'
import { tokenStorage } from '@/lib/tokenStorage'
import { queryClient } from '@/lib/queryClient'
import SidebarLeft from '@/components/layout/SidebarLeft'
import ConfirmModal from '@/components/ui/ConfirmModal'

export default function ProfilePage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { data: conversations = [] } = useConversationsList()
  const { data: games = [] } = useUserGames()
  const deleteConv = useDeleteConversation()

  const [deleteAccountOpen, setDeleteAccountOpen] = useState(false)
  const [deleteConvsOpen, setDeleteConvsOpen] = useState(false)

  const completedCount = games.filter(g => g.status === 'completed').length
  const createdAt = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('fr-FR', { year: 'numeric', month: 'long', day: 'numeric' })
    : '—'

  const initial = user?.username?.[0]?.toUpperCase() ?? user?.email?.[0]?.toUpperCase() ?? '?'

  async function handleDeleteAccount() {
    try {
      await apiClient.delete('/users/me')
    } catch { /* ignore */ }
    tokenStorage.clear()
    queryClient.clear()
    navigate('/login', { replace: true })
  }

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  async function handleDeleteAllConvs() {
    await Promise.all(conversations.map(c => deleteConv.mutateAsync(c.id)))
    setDeleteConvsOpen(false)
  }

  return (
    <div className="flex h-full">
      <SidebarLeft />

      <main className="flex-1 overflow-y-auto px-6 py-10">
        <div className="mx-auto max-w-[560px]">
          {/* Header */}
          <div className="mb-8 flex items-center gap-4">
            <div
              className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-full text-xl font-semibold text-white"
              style={{ background: 'linear-gradient(135deg, #1035C0, #5B7EFF)' }}
            >
              {initial}
            </div>
            <div>
              <h1 className="text-[22px] font-semibold text-primary">{user?.username}</h1>
              <p className="text-[14px] text-muted">{user?.email}</p>
            </div>
          </div>

          {/* Stats */}
          <div className="mb-4 grid grid-cols-3 gap-3">
            {[
              { value: games.length, label: 'Jeux' },
              { value: conversations.length, label: 'Conversations' },
              { value: completedCount, label: 'Terminés' },
            ].map(({ value, label }) => (
              <div key={label} className="rounded-[10px] border border-border bg-elevated p-4 text-center">
                <div className="text-2xl font-bold text-accent-soft">{value}</div>
                <div className="mt-0.5 text-[12px] text-muted">{label}</div>
              </div>
            ))}
          </div>

          {/* Compte */}
          <div className="mb-4 overflow-hidden rounded-[16px] border border-border bg-elevated">
            <div className="border-b border-border px-5 py-3.5 text-[12px] font-semibold uppercase tracking-[0.8px] text-faint">
              Compte
            </div>
            {[
              { label: 'Email', value: user?.email },
              { label: 'Pseudo', value: user?.username },
              { label: 'Membre depuis', value: createdAt },
              { label: 'Statut', value: user?.is_verified ? 'Vérifié' : 'Non vérifié' },
            ].map(({ label, value }) => (
              <div key={label} className="flex items-center justify-between border-b border-border/60 px-5 py-4 last:border-b-0">
                <span className="text-[13px] text-muted">{label}</span>
                <span className="text-[14px] font-medium text-primary">{value}</span>
              </div>
            ))}
          </div>

          {/* Actions */}
          <div className="overflow-hidden rounded-[16px] border border-border bg-elevated">
            <div className="border-b border-border px-5 py-3.5 text-[12px] font-semibold uppercase tracking-[0.8px] text-faint">
              Actions
            </div>
            <div className="flex flex-col gap-2 p-4">
              <button
                onClick={handleLogout}
                className="w-full rounded-[10px] border border-border py-3 text-[14px] font-medium text-primary transition-all hover:bg-hover"
              >
                Se déconnecter
              </button>
              {conversations.length > 0 && (
                <button
                  onClick={() => setDeleteConvsOpen(true)}
                  className="w-full rounded-[10px] border border-border py-3 text-[14px] font-medium text-muted transition-all hover:bg-hover hover:text-primary"
                >
                  Supprimer toutes les conversations
                </button>
              )}
              <button
                onClick={() => setDeleteAccountOpen(true)}
                className="w-full rounded-[10px] border border-danger/30 bg-danger-dim py-3 text-[14px] font-medium text-danger transition-all hover:bg-danger/20"
              >
                Supprimer mon compte
              </button>
            </div>
          </div>
        </div>
      </main>

      <ConfirmModal
        open={deleteAccountOpen}
        title="Supprimer ton compte"
        message="Cette action est irréversible. Toutes tes conversations et données seront supprimées définitivement."
        confirmLabel="Supprimer mon compte"
        danger
        onConfirm={handleDeleteAccount}
        onCancel={() => setDeleteAccountOpen(false)}
      />

      <ConfirmModal
        open={deleteConvsOpen}
        title={`Supprimer ${conversations.length} conversation(s)`}
        message="Toutes tes conversations seront supprimées définitivement."
        confirmLabel="Tout supprimer"
        danger
        onConfirm={handleDeleteAllConvs}
        onCancel={() => setDeleteConvsOpen(false)}
      />
    </div>
  )
}
