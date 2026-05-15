import { useState } from 'react'
import axios from 'axios'
import { useXboxPreview, useXboxImport } from '@/hooks/useUserGames'
import type { XboxConfirmItem } from '@/api/userGames'
import XboxValidationList from './XboxValidationList'

function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (detail === 'xbox_invalid_gamertag') return 'Gamertag introuvable. Vérifie l\'orthographe.'
    if (detail === 'xbox_profile_private') return 'Profil Xbox privé. Va dans les paramètres Xbox → Confidentialité → "Historique de jeux et d\'applications" → Public.'
    if (detail === 'xbox_quota_exceeded') return 'Limite de requêtes atteinte. Réessaie dans quelques minutes.'
    if (detail === 'xbox_api_unavailable' || detail === 'xbox_api_key_invalid') return 'Service Xbox temporairement indisponible. Réessaie dans quelques instants.'
  }
  return 'Impossible de charger ta bibliothèque. Réessaie plus tard.'
}

export default function XboxImportPanel({ onDone }: { onDone: () => void }) {
  const [input, setInput] = useState('')
  const [preview, setPreview] = useState<import('@/api/userGames').XboxPreviewItem[] | null>(null)
  const [importResult, setImportResult] = useState<{ imported: number; skipped: number } | null>(null)

  const previewMutation = useXboxPreview()
  const importMutation = useXboxImport()

  const handleLoad = () => {
    if (!input.trim()) return
    previewMutation.mutate(input.trim(), {
      onSuccess: (items) => setPreview(items),
    })
  }

  const handleImport = (items: XboxConfirmItem[]) => {
    importMutation.mutate(items, {
      onSuccess: (result) => setImportResult(result),
    })
  }

  if (importResult) {
    return (
      <div className="flex flex-col items-center gap-4 py-6 text-center">
        <div className="text-3xl">🎮</div>
        <div>
          <p className="text-[14px] font-semibold text-primary">
            {importResult.imported} jeu{importResult.imported > 1 ? 'x' : ''} importé{importResult.imported > 1 ? 's' : ''} !
          </p>
          {importResult.skipped > 0 && (
            <p className="mt-1 text-[12px] text-faint">{importResult.skipped} jeu{importResult.skipped > 1 ? 'x' : ''} ignoré{importResult.skipped > 1 ? 's' : ''} (déjà dans ta biblio)</p>
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
          <p className="py-4 text-center text-[12px] text-faint">Aucun jeu trouvé sur ce profil Xbox.</p>
        ) : (
          <XboxValidationList
            items={preview}
            onImport={handleImport}
            importing={importMutation.isPending}
          />
        )}
        {importMutation.isError && (
          <p className="text-[12px] text-[#FF6B84]">Erreur lors de l'import. Réessaie.</p>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <label className="mb-1.5 block text-[12px] font-semibold uppercase tracking-[0.5px] text-muted">
          Gamertag Xbox
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleLoad() }}
            autoFocus
            placeholder="Major Nelson"
            className="flex-1 rounded-[8px] border border-border bg-input-bg px-3 py-2 text-[13px] text-primary outline-none placeholder:text-faint focus:border-accent/40"
          />
          <button
            type="button"
            onClick={handleLoad}
            disabled={!input.trim() || previewMutation.isPending}
            className="flex-shrink-0 rounded-[8px] bg-accent px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {previewMutation.isPending ? (
              <span className="flex items-center gap-2">
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Chargement…
              </span>
            ) : 'Charger ma bibliothèque'}
          </button>
        </div>
        <p className="mt-1.5 text-[12px] text-faint">
          Uniquement le gamertag public — jamais un mot de passe Microsoft.
        </p>
      </div>

      {/* Warning box */}
      <div className="rounded-[8px] border border-border/60 bg-panel px-3 py-2.5 text-[13px] text-faint leading-relaxed space-y-1">
        <p className="font-medium text-muted">⚠ Ce que tu verras dans la liste</p>
        <p>Seuls les jeux où tu as débloqué <span className="text-muted">au moins un succès</span> seront importés. Tes jeux jamais lancés ou sans succès n'apparaîtront pas.</p>
        <p>Ton profil Xbox doit avoir <span className="text-muted">"Historique de jeux et d'applications"</span> en public — va dans <span className="text-muted">Paramètres Xbox → Confidentialité</span>.</p>
      </div>

      {previewMutation.isError && (
        <p className="text-[12px] text-[#FF6B84]">{errorMessage(previewMutation.error)}</p>
      )}
    </div>
  )
}
