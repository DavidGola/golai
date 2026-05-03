import type { UserGameStatus } from '@/types/userGame'

const CONFIG: Record<UserGameStatus, { label: string; className: string }> = {
  completed:   { label: 'Terminé',   className: 'bg-[rgba(40,200,100,0.12)] text-[#5DE89E] border border-[rgba(40,200,100,0.25)]' },
  todo:        { label: 'À faire',   className: 'bg-[rgba(91,126,255,0.08)] text-muted border border-border' },
  dropped:     { label: 'Abandonné', className: 'bg-danger-dim text-[#FF6B84] border border-danger/25' },
  not_started: { label: 'Intouché',  className: 'bg-[rgba(255,170,50,0.1)] text-[#FFAA32] border border-[rgba(255,170,50,0.25)]' },
}

export default function StatusBadge({ status }: { status: UserGameStatus }) {
  const { label, className } = CONFIG[status]
  return (
    <span className={`rounded-full px-[7px] py-0.5 text-[10px] font-semibold uppercase tracking-[0.3px] whitespace-nowrap ${className}`}>
      {label}
    </span>
  )
}
