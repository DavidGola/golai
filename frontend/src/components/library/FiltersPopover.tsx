import { useState, useRef, useEffect } from 'react'
import type { UserGameStatus } from '@/types/userGame'

const STATUS_CONFIG: Record<UserGameStatus, { label: string; activeClass: string }> = {
  completed:   { label: 'Terminé',   activeClass: 'bg-[rgba(40,200,100,0.12)] text-[#5DE89E] border-[rgba(40,200,100,0.25)]' },
  todo:        { label: 'À faire',   activeClass: 'bg-[rgba(91,126,255,0.08)] text-muted border-border' },
  dropped:     { label: 'Abandonné', activeClass: 'bg-danger-dim text-[#FF6B84] border-danger/25' },
  not_started: { label: 'Intouché',  activeClass: 'bg-[rgba(255,170,50,0.1)] text-[#FFAA32] border-[rgba(255,170,50,0.25)]' },
}

const STATUS_KEYS: UserGameStatus[] = ['completed', 'todo', 'dropped', 'not_started']

interface Genre {
  id: number
  name: string
}

interface Props {
  statusValue: UserGameStatus[]
  genreValue: number[]
  availableGenres: Genre[]
  onChange: (status: UserGameStatus[], genres: number[]) => void
}

interface FilterGroupProps<T extends string | number> {
  title: string
  items: { value: T; label: string; activeClass?: string }[]
  selected: T[]
  onToggle: (v: T) => void
}

function FilterGroup<T extends string | number>({ title, items, selected, onToggle }: FilterGroupProps<T>) {
  const [search, setSearch] = useState('')
  const filtered = search
    ? items.filter(i => i.label.toLowerCase().includes(search.toLowerCase()))
    : items
  const showSearch = items.length > 8

  return (
    <div>
      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-faint">{title}</p>
      {showSearch && (
        <input
          type="search"
          placeholder="Filtrer…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="mb-2 w-full rounded-[6px] border border-border bg-input-bg px-2.5 py-1 text-[11px] text-primary outline-none placeholder:text-faint focus:border-accent/40"
        />
      )}
      <div className="flex flex-wrap gap-1">
        {filtered.map(item => {
          const active = selected.includes(item.value)
          return (
            <button
              key={String(item.value)}
              onClick={() => onToggle(item.value)}
              className={[
                'rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-all',
                active
                  ? item.activeClass ?? 'bg-accent-dim text-accent-soft border-accent/35'
                  : 'border-border text-muted hover:border-faint hover:text-primary',
              ].join(' ')}
            >
              {item.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function toggle<T>(arr: T[], v: T): T[] {
  return arr.includes(v) ? arr.filter(x => x !== v) : [...arr, v]
}

const POPOVER_WIDTH = 300

export default function FiltersPopover({ statusValue, genreValue, availableGenres, onChange }: Props) {
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

  const total = statusValue.length + genreValue.length

  const statusItems = STATUS_KEYS.map(s => ({
    value: s,
    label: STATUS_CONFIG[s].label,
    activeClass: STATUS_CONFIG[s].activeClass,
  }))

  const genreItems = [...availableGenres]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map(g => ({ value: g.id, label: g.name }))

  return (
    <>
      <button
        ref={buttonRef}
        onClick={handleOpen}
        className={[
          'flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-all',
          total > 0
            ? 'border-accent/35 bg-accent-dim text-accent-soft'
            : 'border-border text-muted hover:border-faint hover:text-primary',
        ].join(' ')}
      >
        <span>⚐ Filtres</span>
        {total > 0 && <span>({total})</span>}
      </button>

      {open && (
        <div
          ref={popoverRef}
          className="fixed z-50 overflow-y-auto rounded-[10px] border border-border bg-elevated p-3 shadow-lg"
          style={{
            top: pos.top,
            left: pos.left,
            width: POPOVER_WIDTH,
            maxHeight: 'min(420px, calc(100vh - 120px))',
          }}
        >
          <div className="flex flex-col gap-4">
            <FilterGroup<UserGameStatus>
              title="Statut"
              items={statusItems}
              selected={statusValue}
              onToggle={v => onChange(toggle(statusValue, v), genreValue)}
            />
            {genreItems.length > 0 && (
              <FilterGroup<number>
                title="Genre"
                items={genreItems}
                selected={genreValue}
                onToggle={v => onChange(statusValue, toggle(genreValue, v))}
              />
            )}
          </div>

          {total > 0 && (
            <button
              onClick={() => onChange([], [])}
              className="mt-3 w-full rounded-[6px] border border-border py-1 text-[11px] text-faint transition-colors hover:border-faint hover:text-muted"
            >
              Tout effacer
            </button>
          )}
        </div>
      )}
    </>
  )
}
