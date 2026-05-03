import { useState } from 'react'
import axios from 'axios'
import { useSteamPreview, useSteamImport } from '@/hooks/useUserGames'
import type { SteamPreviewItem, SteamConfirmItem } from '@/api/userGames'
import SteamValidationList from './SteamValidationList'

function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (detail === 'steam_invalid_input') return "Format invalide. Colle l'URL de ton profil Steam ou ton SteamID64."
    if (detail === 'steam_profile_private') return "Profil introuvable ou privé. Vérifie que « Mon profil » et « Détails du jeu » sont en Public dans tes paramètres Steam — le changement peut prendre quelques minutes."
  }
  return 'Impossible de charger ta bibliothèque. Réessaie plus tard.'
}

export default function SteamImportPanel({ onDone }: { onDone: () => void }) {
  const [input, setInput] = useState('')
  const [preview, setPreview] = useState<SteamPreviewItem[] | null>(null)
  const [importResult, setImportResult] = useState<{ imported: number; skipped: number } | null>(null)

  const previewMutation = useSteamPreview()
  const importMutation = useSteamImport()

  const handleLoad = () => {
    if (!input.trim()) return
    previewMutation.mutate(input.trim(), {
      onSuccess: (items) => setPreview(items),
    })
  }

  const handleImport = (items: SteamConfirmItem[]) => {
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
          <p className="py-4 text-center text-[12px] text-faint">Aucun jeu trouvé sur ce profil Steam.</p>
        ) : (
          <SteamValidationList
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
          Profil Steam
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleLoad() }}
            autoFocus
            placeholder="steamcommunity.com/id/… ou SteamID64"
            className="flex-1 rounded-[8px] border border-border bg-input-bg px-3 py-2 text-[13px] text-primary outline-none placeholder:text-faint focus:border-accent/40"
          />
          <button
            type="button"
            onClick={handleLoad}
            disabled={!input.trim() || previewMutation.isPending}
            className="flex-shrink-0 rounded-[8px] bg-accent px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {previewMutation.isPending ? 'Chargement…' : 'Charger'}
          </button>
        </div>
      </div>

      <div className="rounded-[8px] border border-border/60 bg-panel px-3 py-2.5 text-[12px] text-faint leading-relaxed space-y-1">
        <p>Deux paramètres doivent être en <span className="text-muted font-medium">Public</span> dans Steam :</p>
        <p>· <span className="text-muted">Mon profil</span> → Public</p>
        <p>· <span className="text-muted">Détails du jeu</span> → Public</p>
        <p className="mt-1">Chemin : <span className="text-muted">Profil → Modifier le profil → Paramètres de confidentialité</span></p>
        <p className="text-faint/70">Le changement peut prendre quelques minutes à être pris en compte.</p>
      </div>

      {previewMutation.isError && (
        <p className="text-[12px] text-[#FF6B84]">{errorMessage(previewMutation.error)}</p>
      )}
    </div>
  )
}
