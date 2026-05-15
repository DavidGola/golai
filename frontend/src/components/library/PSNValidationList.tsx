import { useState } from 'react'
import type { PSNPreviewItem, PSNConfirmItem } from '@/api/userGames'
import type { UserGameStatus } from '@/types/userGame'

const STATUS_OPTIONS: { value: UserGameStatus; label: string }[] = [
  { value: 'not_started', label: 'Intouché' },
  { value: 'completed',   label: 'Terminé' },
  { value: 'todo',        label: 'À faire' },
  { value: 'dropped',     label: 'Abandonné' },
]

type RowState = {
  checked: boolean
  status: UserGameStatus | null
  rating: string
  review: string
  expanded: boolean
}

interface Props {
  items: PSNPreviewItem[]
  onImport: (items: PSNConfirmItem[]) => void
  importing: boolean
}

export default function PSNValidationList({ items, onImport, importing }: Props) {
  const [rows, setRows] = useState<RowState[]>(() =>
    items.map(item => ({
      checked: !item.already_in_library,
      status: null,
      rating: '',
      review: '',
      expanded: false,
    }))
  )

  const updateRow = (i: number, patch: Partial<RowState>) =>
    setRows(prev => prev.map((r, idx) => idx === i ? { ...r, ...patch } : r))

  const checkedCount = rows.filter((r, i) => r.checked && !items[i]!.already_in_library).length
  const allChecked = rows.every((r, i) => items[i]!.already_in_library || r.checked)
  const noneChecked = rows.every((r, i) => items[i]!.already_in_library || !r.checked)

  const toggleAll = () => {
    const next = !allChecked
    setRows(prev => prev.map((r, i) => items[i]!.already_in_library ? r : { ...r, checked: next }))
  }

  const handleImport = () => {
    const payload: PSNConfirmItem[] = rows
      .map((r, i) => ({ r, item: items[i]! }))
      .filter(({ r, item }) => r.checked && !item.already_in_library)
      .map(({ r, item }) => ({
        game_id: item.game_id,
        status: r.status,
        user_rating: r.rating ? Number(r.rating) : null,
        review: r.review.trim() || null,
        hours_played: item.hours_played,
      }))
    onImport(payload)
  }

  const newCount = items.filter(item => !item.already_in_library).length
  const alreadyCount = items.filter(item => item.already_in_library).length

  return (
    <div className="flex flex-col gap-3">
      {/* Summary + bulk actions */}
      <div className="flex items-center justify-between">
        <p className="text-[12px] text-muted">
          <span className="font-semibold text-primary">{items.length}</span> jeux trouvés
          {newCount > 0 && <> · <span className="text-accent-soft">{newCount} nouveaux</span></>}
          {alreadyCount > 0 && <> · <span className="text-faint">{alreadyCount} déjà dans ta biblio</span></>}
        </p>
        <button
          type="button"
          onClick={toggleAll}
          className="text-[12px] text-accent-soft hover:underline"
        >
          {allChecked && !noneChecked ? 'Tout décocher' : 'Tout cocher'}
        </button>
      </div>

      {/* Game rows */}
      <div className={`relative max-h-[320px] overflow-y-auto rounded-[10px] border border-border ${importing ? 'pointer-events-none' : ''}`}>
        {importing && (
          <div className="absolute inset-0 z-10 flex items-center justify-center rounded-[10px] bg-elevated/70 backdrop-blur-[2px]">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-border border-t-accent" />
          </div>
        )}
        {items.map((item, i) => {
          const row = rows[i]!
          const disabled = item.already_in_library
          return (
            <div key={item.game_id} className={`border-b border-border/60 last:border-b-0 ${disabled ? 'opacity-50' : ''}`}>
              <div className="flex items-center gap-2.5 px-3 py-2.5">
                {/* Checkbox */}
                <input
                  type="checkbox"
                  checked={row.checked}
                  disabled={disabled}
                  onChange={e => updateRow(i, { checked: e.target.checked })}
                  className="h-4 w-4 flex-shrink-0 accent-accent cursor-pointer disabled:cursor-default"
                />
                {/* Cover */}
                <div className="h-[32px] w-[48px] flex-shrink-0 overflow-hidden rounded-[4px] bg-panel">
                  {item.cover_url && (
                    <img src={item.cover_url} alt="" className="h-full w-full object-cover" />
                  )}
                </div>
                {/* Title + trophy progress + playtime */}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[12px] font-medium text-primary">{item.title}</p>
                  <div className="flex items-center gap-2 text-[12px] text-faint">
                    {item.trophy_progress_pct != null && (
                      <span>{item.trophy_progress_pct}% trophées</span>
                    )}
                    {item.hours_played != null && item.hours_played > 0 && (
                      <span>{item.hours_played}h jouées</span>
                    )}
                  </div>
                </div>
                {/* Already in library badge */}
                {disabled && (
                  <span className="flex-shrink-0 rounded-full border border-border px-2 py-0.5 text-[12px] text-faint">
                    déjà ajouté
                  </span>
                )}
                {/* Status select */}
                {!disabled && (
                  <select
                    value={row.status ?? ''}
                    onChange={e => updateRow(i, { status: (e.target.value || null) as UserGameStatus | null })}
                    className="flex-shrink-0 rounded-[6px] border border-border bg-panel px-2 py-1 text-[12px] text-primary outline-none focus:border-accent/40"
                  >
                    <option value="">—</option>
                    {STATUS_OPTIONS.map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                )}
                {/* Expand toggle */}
                {!disabled && (
                  <button
                    type="button"
                    onClick={() => updateRow(i, { expanded: !row.expanded })}
                    className={`flex-shrink-0 text-[14px] transition-colors ${row.expanded ? 'text-accent-soft' : 'text-faint hover:text-muted'}`}
                    title="Note et commentaire"
                  >
                    ✎
                  </button>
                )}
              </div>
              {/* Expanded note + review */}
              {!disabled && row.expanded && (
                <div className="flex items-start gap-3 border-t border-border/40 bg-panel/50 px-3 py-3">
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[12px] font-semibold uppercase tracking-wide text-faint">Note</label>
                    <input
                      type="number"
                      min={1}
                      max={10}
                      value={row.rating}
                      onChange={e => updateRow(i, { rating: e.target.value })}
                      placeholder="—"
                      className="w-[60px] rounded-[6px] border border-border bg-input-bg px-2.5 py-1.5 text-[12px] text-primary outline-none placeholder:text-faint focus:border-accent/40"
                    />
                  </div>
                  <div className="flex flex-1 flex-col gap-1.5">
                    <label className="text-[12px] font-semibold uppercase tracking-wide text-faint">Avis</label>
                    <textarea
                      value={row.review}
                      onChange={e => updateRow(i, { review: e.target.value })}
                      rows={2}
                      placeholder="Tes impressions…"
                      className="w-full resize-none rounded-[6px] border border-border bg-input-bg px-2.5 py-1.5 text-[12px] text-primary outline-none placeholder:text-faint focus:border-accent/40"
                    />
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Import button */}
      <button
        type="button"
        onClick={handleImport}
        disabled={checkedCount === 0 || importing}
        className="w-full rounded-[8px] bg-accent py-2 text-[13px] font-medium text-white transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {importing ? (
          <span className="flex items-center justify-center gap-2">
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            Importation…
          </span>
        ) : checkedCount === 0
          ? 'Aucun jeu sélectionné'
          : `Importer ${checkedCount} jeu${checkedCount > 1 ? 'x' : ''}`}
      </button>
    </div>
  )
}
