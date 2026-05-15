# Politique de confidentialité

*Dernière mise à jour : 16 mai 2026*

---

## 1. Responsable de traitement

Les données collectées sur GolAi sont traitées par :

**David Gola** — Ingénieur IA indépendant  
Contact : [golaichat@outlook.com](mailto:golaichat@outlook.com)

---

## 2. Données collectées

Lors de l'utilisation de GolAi, les données suivantes sont susceptibles d'être collectées :

- **Compte** : adresse e-mail et mot de passe haché (fournis à l'inscription).
- **Bibliothèque de jeux** : liste des jeux importés depuis Steam ou d'autres plateformes (identifiants de jeux, statuts, notes, temps de jeu).
- **Conversations** : messages envoyés à l'agent IA et réponses reçues.
- **Traces techniques** : données de diagnostic transmises à nos prestataires de monitoring (voir section 4).

---

## 3. Finalités du traitement

Les données sont utilisées pour :

- **Faire fonctionner le service** : personnaliser les recommandations de jeux en fonction de votre bibliothèque et de vos échanges avec l'agent.
- **Améliorer la qualité** : analyser les traces d'erreurs et de performance pour corriger les bugs et améliorer les réponses de l'agent.
- **Sécuriser le service** : détecter les usages abusifs et protéger les données des autres utilisateurs.

---

## 4. Sous-traitants et transferts

GolAi fait appel aux prestataires suivants, chacun soumis à ses propres politiques de confidentialité :

| Prestataire | Rôle | Localisation |
|---|---|---|
| **Anthropic** | Modèle de langage (agent IA) — les messages de la conversation sont envoyés à Anthropic pour générer les réponses. | États-Unis |
| **Valve / Steam** | Import de la bibliothèque de jeux (si vous liez votre compte Steam). | États-Unis |
| **Langfuse** | Traces des appels au modèle IA (tokens, latence, contenu des échanges si activé). | Europe (UE) |
| **Sentry** | Monitoring des erreurs frontend et backend. | États-Unis |
| **Backblaze B2** | Sauvegardes chiffrées de la base de données. | États-Unis |

Les transferts vers les États-Unis sont effectués sur la base des clauses contractuelles types (CCT) ou des garanties équivalentes reconnues par la réglementation européenne.

---

## 5. Durée de conservation

- **Conversations** : conservées 12 mois glissants à compter de leur date de création, puis supprimées automatiquement.
- **Compte et bibliothèque** : conservés jusqu'à la suppression du compte par l'utilisateur.
- **Traces Sentry / Langfuse** : selon les politiques de conservation propres à chaque prestataire (généralement 30 à 90 jours).

---

## 6. Vos droits (RGPD)

Conformément au Règlement Général sur la Protection des Données (RGPD), vous disposez des droits suivants :

- **Droit d'accès** : obtenir une copie des données vous concernant.
- **Droit de rectification** : corriger des données inexactes.
- **Droit à l'effacement** : supprimer votre compte et toutes les données associées depuis la page [/profile](/profile).
- **Droit d'opposition** : vous opposer à certains traitements.
- **Droit à la portabilité** : recevoir vos données dans un format structuré et lisible.

Pour exercer ces droits, contactez : [golaichat@outlook.com](mailto:golaichat@outlook.com)

En cas de réponse insatisfaisante, vous pouvez introduire une réclamation auprès de la **CNIL** : [cnil.fr](https://www.cnil.fr).

---

## 7. Cookies et tracking

GolAi n'utilise **aucun cookie de traçage tiers**. Seul un token d'authentification JWT est stocké dans le `localStorage` de votre navigateur pour maintenir votre session. Aucune donnée n'est transmise à des régies publicitaires.

---

## 8. Sécurité

Les mots de passe sont hachés (bcrypt). Les sauvegardes de la base de données sont chiffrées. Les échanges entre votre navigateur et le serveur sont sécurisés par HTTPS (TLS 1.2+).
