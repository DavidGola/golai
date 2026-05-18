import { useState, type ReactNode } from 'react'
import axios from 'axios'
import type { UseMutationResult } from '@tanstack/react-query'

/**
 * Generic panel for "import library from external store" flows.
 *
 * State machine identique pour Steam / PSN / Xbox (et futurs Nintendo /
 * Epic / GOG) : input → preview list → import result.
 * La config par source (voir libraryImportSources.ts) capture tout ce qui
 * varie : labels, textes d'aide, mapping d'erreurs API, hooks de mutation,
 * et le rendu de la ValidationList propre à chaque source.
 */
export interface LibraryImportSourceConfig<TPreview, TConfirm, TRawPreview = TPreview[]> {
  inputLabel: string                            // "Profil Steam", "PSN Online ID"…
  inputPlaceholder: string                      // "steamcommunity.com/id/…"
  inputHelperText?: string                      // sous l'input (PSN/Xbox en ont)
  helpBox: ReactNode                            // bloc warning pré-load
  emptyMessage: string                          // "Aucun jeu trouvé sur ce profil Steam"
  loadingWithSpinner?: boolean                  // PSN/Xbox = true, Steam = false

  /** Mapping `detail` HTTP → message FR. La key par défaut est le message générique. */
  errorMessages: Record<string, string>

  usePreviewMutation: () => UseMutationResult<TRawPreview, unknown, string>
  /** Extrait les items et l'identifiant de compte depuis le résultat brut du preview.
   * Pour PSN/Xbox, account = inputValue. Pour Steam, account = resolved_steam_id. */
  extractPreview: (raw: TRawPreview, inputValue: string) => { items: TPreview[]; account: string }
  useImportMutation: () => UseMutationResult<{ imported: number; skipped: number }, unknown, { items: TConfirm[]; account: string }>

  renderValidationList: (props: {
    items: TPreview[]
    onImport: (items: TConfirm[]) => void
    importing: boolean
  }) => ReactNode
}

function buildErrorMessage(err: unknown, mapping: Record<string, string>): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string' && mapping[detail]) {
      return mapping[detail]
    }
  }
  return 'Impossible de charger ta bibliothèque. Réessaie plus tard.'
}

export default function LibraryImportPanel<TPreview, TConfirm, TRawPreview = TPreview[]>({
  source,
  onDone,
}: {
  source: LibraryImportSourceConfig<TPreview, TConfirm, TRawPreview>
  onDone: () => void
}) {
  const [input, setInput] = useState('')
  const [preview, setPreview] = useState<TPreview[] | null>(null)
  const [account, setAccount] = useState('')
  const [importResult, setImportResult] = useState<{ imported: number; skipped: number } | null>(null)

  const previewMutation = source.usePreviewMutation()
  const importMutation = source.useImportMutation()

  const handleLoad = () => {
    if (!input.trim()) return
    previewMutation.mutate(input.trim(), {
      onSuccess: (raw) => {
        const { items, account: resolvedAccount } = source.extractPreview(raw, input.trim())
        setPreview(items)
        setAccount(resolvedAccount)
      },
    })
  }

  const handleImport = (items: TConfirm[]) => {
    importMutation.mutate({ items, account }, {
      onSuccess: (result) => setImportResult(result),
    })
  }

  // ─── Écran 3 : résultat d'import ──────────────────────────────────────────
  if (importResult) {
    return (
      <div className="flex flex-col items-center gap-4 py-6 text-center">
        <div className="text-3xl">🎮</div>
        <div>
          <p className="text-[14px] font-semibold text-primary">
            {importResult.imported} jeu{importResult.imported > 1 ? 'x' : ''} importé{importResult.imported > 1 ? 's' : ''} !
          </p>
          {importResult.skipped > 0 && (
            <p className="mt-1 text-[12px] text-faint">
              {importResult.skipped} jeu{importResult.skipped > 1 ? 'x' : ''} ignoré{importResult.skipped > 1 ? 's' : ''} (déjà dans ta biblio)
            </p>
          )}
        </div>
        <button
          onClick={onDone}
          className="rounded-[8px] bg-accent px-5 py-2 text-[13px] font-medium text-white hover:bg-accent/90"
        >
          Voir ma bibliothèque
        </button>
      </div>
    )
  }

  // ─── Écran 2 : preview / validation ───────────────────────────────────────
  if (preview) {
    return (
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => { setPreview(null); previewMutation.reset() }}
            className="text-[12px] text-faint hover:text-muted"
          >
            ← Retour
          </button>
          <span className="text-[12px] text-muted">Validation de l'import</span>
        </div>
        {preview.length === 0 ? (
          <p className="py-4 text-center text-[12px] text-faint">{source.emptyMessage}</p>
        ) : (
          source.renderValidationList({
            items: preview,
            onImport: handleImport,
            importing: importMutation.isPending,
          })
        )}
        {importMutation.isError && (
          <p className="text-[12px] text-[#FF6B84]">
            {buildErrorMessage(importMutation.error, source.errorMessages)}
          </p>
        )}
      </div>
    )
  }

  // ─── Écran 1 : saisie input ───────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-4">
      <div>
        <label className="mb-1.5 block text-[12px] font-semibold uppercase tracking-[0.5px] text-muted">
          {source.inputLabel}
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleLoad() }}
            autoFocus
            placeholder={source.inputPlaceholder}
            className="flex-1 rounded-[8px] border border-border bg-input-bg px-3 py-2 text-[13px] text-primary outline-none placeholder:text-faint focus:border-accent/40"
          />
          <button
            type="button"
            onClick={handleLoad}
            disabled={!input.trim() || previewMutation.isPending}
            className="flex-shrink-0 rounded-[8px] bg-accent px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {previewMutation.isPending ? (
              source.loadingWithSpinner ? (
                <span className="flex items-center gap-2">
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  Chargement…
                </span>
              ) : 'Chargement…'
            ) : (
              source.loadingWithSpinner ? 'Charger ma bibliothèque' : 'Charger'
            )}
          </button>
        </div>
        {source.inputHelperText && (
          <p className="mt-1.5 text-[12px] text-faint">{source.inputHelperText}</p>
        )}
      </div>

      {source.helpBox}

      {previewMutation.isError && (
        <p className="text-[12px] text-[#FF6B84]">
          {buildErrorMessage(previewMutation.error, source.errorMessages)}
        </p>
      )}
    </div>
  )
}
