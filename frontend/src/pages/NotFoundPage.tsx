import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 bg-base text-primary">
      <span className="font-display text-4xl text-accent">404</span>
      <p className="text-muted">Page introuvable</p>
      <Link to="/" className="text-accent-soft underline">Retour à l'accueil</Link>
    </div>
  )
}
