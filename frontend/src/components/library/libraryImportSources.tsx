/**
 * Configs Steam/PSN/Xbox pour <LibraryImportPanel source={...} />.
 *
 * Ajouter Nintendo / Epic / GOG = créer un nouvel objet config ici + sa
 * ValidationList. Aucun nouveau panel à écrire.
 */

import {
  useSteamPreview, useSteamImport,
  usePSNPreview, usePSNImport,
  useXboxPreview, useXboxImport,
} from '@/hooks/useUserGames'
import type {
  SteamPreviewResult, SteamPreviewItem, SteamConfirmItem,
  PSNPreviewItem, PSNConfirmItem,
  XboxPreviewItem, XboxConfirmItem,
} from '@/api/userGames'
import SteamValidationList from './SteamValidationList'
import PSNValidationList from './PSNValidationList'
import XboxValidationList from './XboxValidationList'
import type { LibraryImportSourceConfig } from './LibraryImportPanel'


export const steamSource: LibraryImportSourceConfig<SteamPreviewItem, SteamConfirmItem, SteamPreviewResult> = {
  inputLabel: 'Profil Steam',
  inputPlaceholder: 'steamcommunity.com/id/… ou SteamID64',
  emptyMessage: 'Aucun jeu trouvé sur ce profil Steam.',
  loadingWithSpinner: false,

  helpBox: (
    <div className="rounded-[8px] border border-border/60 bg-panel px-3 py-2.5 text-[12px] text-faint leading-relaxed space-y-1">
      <p>Deux paramètres doivent être en <span className="text-muted font-medium">Public</span> dans Steam :</p>
      <p>· <span className="text-muted">Mon profil</span> → Public</p>
      <p>· <span className="text-muted">Détails du jeu</span> → Public</p>
      <p className="mt-1">Chemin : <span className="text-muted">Profil → Modifier le profil → Paramètres de confidentialité</span></p>
      <p className="text-faint/70">Le changement peut prendre quelques minutes à être pris en compte.</p>
    </div>
  ),

  errorMessages: {
    steam_invalid_input: "Format invalide. Colle l'URL de ton profil Steam ou ton SteamID64.",
    steam_profile_private: "Profil introuvable ou privé. Vérifie que « Mon profil » et « Détails du jeu » sont en Public dans tes paramètres Steam — le changement peut prendre quelques minutes.",
  },

  usePreviewMutation: useSteamPreview,
  extractPreview: (raw, _input) => ({ items: raw.items, account: raw.resolved_steam_id }),
  useImportMutation: useSteamImport,

  renderValidationList: ({ items, onImport, importing }) => (
    <SteamValidationList items={items} onImport={onImport} importing={importing} />
  ),
}


export const psnSource: LibraryImportSourceConfig<PSNPreviewItem, PSNConfirmItem> = {
  inputLabel: 'PSN Online ID',
  inputPlaceholder: 'Drakey-91',
  inputHelperText: "Uniquement l'ID public (ex : Drakey-91) — jamais un mot de passe.",
  emptyMessage: 'Aucun jeu trouvé sur ce profil PSN.',
  loadingWithSpinner: true,

  helpBox: (
    <div className="rounded-[8px] border border-border/60 bg-panel px-3 py-2.5 text-[13px] text-faint leading-relaxed space-y-1">
      <p className="font-medium text-muted">⚠ Ce que tu verras dans la liste</p>
      <p>Seuls les jeux où tu as débloqué <span className="text-muted">au moins un trophée</span> seront importés. Tes jeux jamais lancés ou sans trophée n'apparaîtront pas.</p>
      <p>Ton profil PSN doit être <span className="text-muted">public</span> — va dans <span className="text-muted">Paramètres → Confidentialité → Jeux → Historique de jeu → Tout le monde</span>.</p>
    </div>
  ),

  errorMessages: {
    psn_invalid_online_id: "PSN Online ID introuvable. Vérifie l'orthographe.",
    psn_profile_private: 'Profil PSN privé. Va dans Paramètres PSN → Confidentialité → "Activité gaming" → Public.',
    psn_npsso_invalid: 'Service PSN temporairement indisponible. Réessaie dans quelques instants.',
    psn_api_unavailable: 'Service PSN temporairement indisponible. Réessaie dans quelques instants.',
    psn_account_already_claimed: 'Ce compte PSN est déjà associé à un autre compte GolAi.',
  },

  usePreviewMutation: usePSNPreview,
  extractPreview: (raw, input) => ({ items: raw, account: input }),
  useImportMutation: usePSNImport,

  renderValidationList: ({ items, onImport, importing }) => (
    <PSNValidationList items={items} onImport={onImport} importing={importing} />
  ),
}


export const xboxSource: LibraryImportSourceConfig<XboxPreviewItem, XboxConfirmItem> = {
  inputLabel: 'Gamertag Xbox',
  inputPlaceholder: 'Major Nelson',
  inputHelperText: 'Uniquement le gamertag public — jamais un mot de passe Microsoft.',
  emptyMessage: 'Aucun jeu trouvé sur ce profil Xbox.',
  loadingWithSpinner: true,

  helpBox: (
    <div className="rounded-[8px] border border-border/60 bg-panel px-3 py-2.5 text-[13px] text-faint leading-relaxed space-y-1">
      <p className="font-medium text-muted">⚠ Ce que tu verras dans la liste</p>
      <p>Seuls les jeux où tu as débloqué <span className="text-muted">au moins un succès</span> seront importés. Tes jeux jamais lancés ou sans succès n'apparaîtront pas.</p>
      <p>Ton profil Xbox doit avoir <span className="text-muted">"Historique de jeux et d'applications"</span> en public — va dans <span className="text-muted">Paramètres Xbox → Confidentialité</span>.</p>
    </div>
  ),

  errorMessages: {
    xbox_invalid_gamertag: "Gamertag introuvable. Vérifie l'orthographe.",
    xbox_profile_private: 'Profil Xbox privé. Va dans les paramètres Xbox → Confidentialité → "Historique de jeux et d\'applications" → Public.',
    xbox_quota_exceeded: 'Limite de requêtes atteinte. Réessaie dans quelques minutes.',
    xbox_api_unavailable: 'Service Xbox temporairement indisponible. Réessaie dans quelques instants.',
    xbox_api_key_invalid: 'Service Xbox temporairement indisponible. Réessaie dans quelques instants.',
  },

  usePreviewMutation: useXboxPreview,
  extractPreview: (raw, input) => ({ items: raw, account: input }),
  useImportMutation: useXboxImport,

  renderValidationList: ({ items, onImport, importing }) => (
    <XboxValidationList items={items} onImport={onImport} importing={importing} />
  ),
}
