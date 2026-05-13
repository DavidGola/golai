import { useState, useRef } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'
import { useConversationsList, useRenameConversation, useDeleteConversation } from '@/hooks/useConversations'
import { formatRelativeDate } from '@/lib/formatDate'
import { cn } from '@/lib/cn'
import ConversationContextMenu from '@/components/conversations/ConversationContextMenu'
import ConfirmModal from '@/components/ui/ConfirmModal'

interface MenuState { id: string; x: number; y: number }

export default function SidebarLeft() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { id: activeId } = useParams<{ id: string }>()
  const { data: conversations = [] } = useConversationsList()
  const rename = useRenameConversation()
  const del = useDeleteConversation()

  const [menu, setMenu] = useState<MenuState | null>(null)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const renameInputRef = useRef<HTMLInputElement>(null)

  const initial = user?.username?.[0]?.toUpperCase() ?? user?.email?.[0]?.toUpperCase() ?? '?'

  function openRename(conv: { id: string; title: string | null }) {
    setRenamingId(conv.id)
    setRenameValue(conv.title ?? '')
    setTimeout(() => renameInputRef.current?.select(), 0)
  }

  async function submitRename() {
    if (!renamingId || !renameValue.trim()) { setRenamingId(null); return }
    await rename.mutateAsync({ id: renamingId, title: renameValue.trim() })
    setRenamingId(null)
  }

  async function confirmDelete() {
    if (!deletingId) return
    await del.mutateAsync(deletingId)
    if (activeId === deletingId) navigate('/chat')
    setDeletingId(null)
  }

  return (
    <aside className="flex w-[300px] flex-shrink-0 flex-col border-r border-border bg-elevated">

      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-4">
        <div
          className="flex h-[28px] w-[28px] flex-shrink-0 items-center justify-center rounded-[7px] bg-accent font-display text-[11px] font-bold text-white"
          style={{ boxShadow: '0 0 14px rgba(16,53,192,0.4)' }}
        >
          G
        </div>
        <span className="font-display text-[14px] font-semibold tracking-[2px] text-primary">GOLAI</span>
      </div>

      {/* New conv */}
      <div className="px-3 pb-2">
        <button
          onClick={() => navigate('/chat')}
          className="flex w-full items-center gap-2.5 rounded-[8px] border border-accent/30 bg-accent-dim px-4 py-3 text-[13px] font-medium text-accent-soft transition-all hover:border-accent/50 hover:bg-accent/18 hover:text-white"
        >
          <span className="text-[15px] leading-none text-accent-soft">＋</span>
          Nouvelle conversation
        </button>
      </div>

      {/* Section label */}
      <p className="px-5 pb-1.5 pt-5 text-[10px] font-semibold uppercase tracking-[1.5px] text-faint">
        Récentes
      </p>

      {/* Conversation list — nav has zero h-padding, buttons own their full width */}
      <nav className="flex flex-1 flex-col overflow-y-auto py-1">
        {conversations.map(conv => {
          const isActive = conv.id === activeId
          return (
            <div key={conv.id} className="relative px-2">
              {renamingId === conv.id ? (
                <input
                  ref={renameInputRef}
                  value={renameValue}
                  onChange={e => setRenameValue(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') void submitRename()
                    if (e.key === 'Escape') setRenamingId(null)
                  }}
                  onBlur={() => void submitRename()}
                  className="my-0.5 w-full rounded-[6px] border border-accent/50 bg-input-bg px-3.5 py-3 text-[13px] text-primary outline-none"
                />
              ) : (
                <button
                  onClick={() => navigate(`/chat/${conv.id}`)}
                  onContextMenu={e => {
                    e.preventDefault()
                    setMenu({ id: conv.id, x: e.clientX, y: e.clientY })
                  }}
                  className={cn(
                    'relative my-0.5 block w-full rounded-[6px] px-3.5 py-3 text-left transition-colors',
                    isActive
                      ? 'bg-[rgba(16,53,192,0.18)] ring-1 ring-inset ring-accent/25'
                      : 'hover:bg-hover',
                  )}
                >
                  {isActive && (
                    <span className="absolute inset-y-2 left-0 w-[3px] rounded-r-full bg-accent" />
                  )}
                  <p className={cn(
                    'truncate text-[13px] font-medium leading-[1.3]',
                    isActive ? 'text-white' : 'text-primary',
                  )}>
                    {conv.title ?? 'Nouvelle conversation'}
                  </p>
                  <p className={cn('mt-1 text-[11px]', isActive ? 'text-accent-soft/60' : 'text-muted')}>
                    {formatRelativeDate(conv.updated_at)}
                  </p>
                </button>
              )}
            </div>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-border p-3">
        <button
          onClick={() => navigate('/profile')}
          className="flex w-full items-center gap-3 rounded-[8px] px-3 py-2.5 text-left transition-colors hover:bg-hover"
        >
          <div
            className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-[13px] font-semibold text-white"
            style={{ background: 'linear-gradient(135deg, #1035C0, #5B7EFF)' }}
          >
            {initial}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-medium text-primary">{user?.username}</p>
            <p className="truncate text-[11px] text-muted">{user?.email}</p>
          </div>
          <span className="text-[14px] text-faint">⚙</span>
        </button>
        <Link
          to="/about"
          className="mt-1 block w-full rounded-[6px] py-2 text-center text-[11px] text-faint transition-colors hover:bg-hover hover:text-muted"
        >
          À propos
        </Link>
        <button
          onClick={logout}
          className="mt-1 w-full rounded-[6px] py-2 text-[11px] text-faint transition-colors hover:bg-hover hover:text-muted"
        >
          Déconnexion
        </button>
      </div>

      {menu && (
        <ConversationContextMenu
          x={menu.x}
          y={menu.y}
          onRename={() => {
            const conv = conversations.find(c => c.id === menu.id)
            if (conv) openRename(conv)
          }}
          onDelete={() => setDeletingId(menu.id)}
          onClose={() => setMenu(null)}
        />
      )}

      <ConfirmModal
        open={!!deletingId}
        title="Supprimer la conversation"
        message="Cette conversation sera supprimée définitivement."
        confirmLabel="Supprimer"
        danger
        onConfirm={confirmDelete}
        onCancel={() => setDeletingId(null)}
      />
    </aside>
  )
}
