import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <div className="flex justify-center gap-5 py-3 text-[12px] text-faint">
      <Link to="/about" className="transition-colors hover:text-muted">À propos</Link>
      <Link to="/privacy" className="transition-colors hover:text-muted">Confidentialité</Link>
    </div>
  )
}
