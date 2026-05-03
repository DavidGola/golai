interface Props {
  open: boolean
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export default function ConfirmModal({
  open,
  title,
  message,
  confirmLabel = 'Confirmer',
  cancelLabel = 'Annuler',
  danger = false,
  onConfirm,
  onCancel,
}: Props) {
  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onMouseDown={e => { if (e.target === e.currentTarget) onCancel() }}
    >
      <div className="w-full max-w-[400px] rounded-[16px] border border-border bg-elevated p-6 shadow-2xl">
        <h2 className="mb-2 text-[16px] font-semibold text-primary">{title}</h2>
        <p className="mb-6 text-[13px] text-muted">{message}</p>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="rounded-[8px] border border-border px-4 py-2 text-[13px] text-muted transition-colors hover:bg-hover hover:text-primary"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={
              danger
                ? 'rounded-[8px] border border-danger/30 bg-danger-dim px-4 py-2 text-[13px] font-medium text-danger transition-colors hover:bg-danger/20'
                : 'rounded-[8px] bg-accent px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-accent/90'
            }
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
