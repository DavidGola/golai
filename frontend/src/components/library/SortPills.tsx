import { useState, useRef, useEffect } from 'react'
import { SORT_LABELS, SORT_DEFAULT_DIR, type SortKey, type SortDir } from '@/lib/sortGames'

const SORT_KEYS: SortKey[] = ['rating', 'playtime', 'steam', 'release', 'title']
const POPOVER_WIDTH = 180

interface Props {
  value: SortKey
  dir: SortDir
  onChange: (key: SortKey, dir: SortDir) => void
}

export default function SortPills({ value, dir, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const buttonRef = useRef<HTMLButtonElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      const inButton = buttonRef.current?.contains(e.target as Node)
      const inPopover = popoverRef.current?.contains(e.target as Node)
      if (!inButton && !inPopover) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const handleOpen = () => {
    if (!open && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect()
      const left = Math.min(rect.left, window.innerWidth - POPOVER_WIDTH - 8)
      setPos({ top: rect.bottom + 6, left })
    }
    setOpen(v => !v)
  }

  const handleSelect = (key: SortKey) => {
    if (key === value) {
      onChange(key, dir === 'asc' ? 'desc' : 'asc')
    } else {
      onChange(key, SORT_DEFAULT_DIR[key])
      setOpen(false)
    }
  }

  return (
    <>
      <button
        ref={buttonRef}
        onClick={handleOpen}
        className="flex items-center gap-1 rounded-full border border-accent/35 bg-accent-tint px-2.5 py-1 text-[11px] font-medium text-accent-soft ring-1 ring-accent/30 transition-all"
      >
        {SORT_LABELS[value]}
        <span className="text-[10px] opacity-70">{dir === 'desc' ? '↓' : '↑'}</span>
        <span className="ml-0.5 text-[10px] opacity-50">▾</span>
      </button>

      {open && (
        <div
          ref={popoverRef}
          className="fixed z-50 rounded-[10px] border border-border bg-elevated py-1.5 shadow-lg"
          style={{ top: pos.top, left: pos.left, width: POPOVER_WIDTH }}
        >
          {SORT_KEYS.map(key => {
            const active = key === value
            return (
              <button
                key={key}
                onClick={() => handleSelect(key)}
                className={[
                  'flex w-full items-center justify-between px-3 py-1.5 text-[12px] transition-colors',
                  active ? 'text-accent-soft' : 'text-muted hover:bg-hover hover:text-primary',
                ].join(' ')}
              >
                <span>{SORT_LABELS[key]}</span>
                {active && (
                  <span className="text-[11px] opacity-70">{dir === 'desc' ? '↓' : '↑'}</span>
                )}
              </button>
            )
          })}
        </div>
      )}
    </>
  )
}
