import { useEffect, useRef } from 'react'

interface Props {
  x: number
  y: number
  onEdit: () => void
  onDelete: () => void
  onClose: () => void
}

export default function GameContextMenu({ x, y, onEdit, onDelete, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', handleDown)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleDown)
      document.removeEventListener('keydown', handleKey)
    }
  }, [onClose])

  const safeX = Math.min(x, window.innerWidth - 168)
  const safeY = Math.min(y, window.innerHeight - 88)

  return (
    <div
      ref={ref}
      style={{ position: 'fixed', top: safeY, left: safeX, zIndex: 100 }}
      className="min-w-[160px] overflow-hidden rounded-[8px] border border-border bg-elevated py-1 shadow-xl"
    >
      <button
        onClick={() => { onEdit(); onClose() }}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] text-primary transition-colors hover:bg-hover"
      >
        <span className="text-faint">✎</span> Modifier
      </button>
      <div className="mx-2 my-1 border-t border-border" />
      <button
        onClick={() => { onDelete(); onClose() }}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] text-danger transition-colors hover:bg-danger/10"
      >
        <span>✕</span> Supprimer
      </button>
    </div>
  )
}
