import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'

const S = {
  page: {
    display: 'flex', minHeight: '100%', alignItems: 'center', justifyContent: 'center',
    background: 'var(--color-base)', padding: '24px',
  } satisfies React.CSSProperties,
  card: {
    width: '100%', maxWidth: 400,
    background: 'var(--color-elevated)', border: '1px solid var(--color-separator)', borderRadius: 16,
    padding: '44px 40px',
    boxShadow: '0 24px 64px rgba(0,0,0,0.6), 0 0 40px var(--color-accent-glow)',
  } satisfies React.CSSProperties,
  logoWrap: { textAlign: 'center', marginBottom: 32 } satisfies React.CSSProperties,
  logoMark: {
    width: 52, height: 52, borderRadius: 12, background: 'var(--color-accent)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    margin: '0 auto 14px',
    fontFamily: "'Orbitron', sans-serif", fontSize: 20, fontWeight: 700, color: '#fff',
    boxShadow: '0 0 24px var(--color-accent-shine)',
  } satisfies React.CSSProperties,
  logoName: {
    fontFamily: "'Orbitron', sans-serif", fontSize: 15, fontWeight: 600,
    letterSpacing: '2.5px', color: 'var(--color-content)',
  } satisfies React.CSSProperties,
  logoTagline: { fontSize: 12, color: 'var(--color-subtle)', marginTop: 6 } satisfies React.CSSProperties,
  title: { fontSize: 20, fontWeight: 600, color: 'var(--color-content)', marginBottom: 6 } satisfies React.CSSProperties,
  subtitle: { fontSize: 13, color: 'var(--color-subtle)', marginBottom: 28 } satisfies React.CSSProperties,
  fieldWrap: { marginBottom: 16 } satisfies React.CSSProperties,
  label: {
    display: 'block', fontSize: 11, fontWeight: 600,
    letterSpacing: '0.6px', textTransform: 'uppercase' as const,
    color: 'var(--color-subtle)', marginBottom: 8,
  } satisfies React.CSSProperties,
  input: {
    width: '100%', background: 'var(--color-input-bg)', border: '1px solid var(--color-separator)',
    borderRadius: 10, padding: '12px 14px', color: 'var(--color-content)',
    fontSize: 14, outline: 'none', boxSizing: 'border-box' as const,
  } satisfies React.CSSProperties,
  errorBox: {
    background: 'var(--color-danger-dim)', border: '1px solid var(--color-danger-ring)',
    borderRadius: 8, padding: '10px 14px', marginBottom: 16,
    fontSize: 13, color: 'var(--color-danger)',
  } satisfies React.CSSProperties,
  btn: {
    width: '100%', background: 'var(--color-accent)', border: 'none', borderRadius: 10,
    padding: '13px', color: '#fff', fontSize: 14, fontWeight: 600,
    cursor: 'pointer', boxShadow: '0 0 16px var(--color-accent-glow)', marginTop: 8,
  } satisfies React.CSSProperties,
  altText: { textAlign: 'center' as const, marginTop: 24, fontSize: 13, color: 'var(--color-subtle)' } satisfies React.CSSProperties,
}

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit() {
    if (password !== confirm) { setError('Les mots de passe ne correspondent pas.'); return }
    setError('')
    setLoading(true)
    try {
      await register(email, password, username)
      navigate('/login', { replace: true, state: { justRegistered: true, email } })
    } catch {
      setError("Erreur lors de l'inscription. Email ou pseudo déjà utilisé ?")
    } finally {
      setLoading(false)
    }
  }

  const fieldProps = (onFocus?: () => void) => ({
    style: S.input,
    onFocus: (e: React.FocusEvent<HTMLInputElement>) => {
      e.currentTarget.style.borderColor = 'var(--color-accent-focus)'
      e.currentTarget.style.boxShadow = '0 0 0 3px var(--color-accent-focus-soft)'
      onFocus?.()
    },
    onBlur: (e: React.FocusEvent<HTMLInputElement>) => {
      e.currentTarget.style.borderColor = 'var(--color-separator)'
      e.currentTarget.style.boxShadow = 'none'
    },
  })

  return (
    <div style={S.page}>
      <div style={S.card}>
        <div style={S.logoWrap}>
          <div style={S.logoMark}>G</div>
          <div style={S.logoName}>GOLAI</div>
          <div style={S.logoTagline}>Recommandation de jeux vidéo</div>
        </div>

        <div style={S.title}>Inscription</div>
        <div style={S.subtitle}>Crée ton compte GolAi.</div>

        <form onSubmit={e => { e.preventDefault(); void submit() }}>
          <div style={S.fieldWrap}>
            <label style={S.label}>Pseudo</label>
            <input type="text" required value={username} onChange={e => setUsername(e.target.value)} placeholder="TonPseudo" {...fieldProps()} />
          </div>
          <div style={S.fieldWrap}>
            <label style={S.label}>Email</label>
            <input type="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="vous@exemple.com" {...fieldProps()} />
          </div>
          <div style={S.fieldWrap}>
            <label style={S.label}>Mot de passe</label>
            <input type="password" required value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" {...fieldProps()} />
          </div>
          <div style={S.fieldWrap}>
            <label style={S.label}>Confirmer</label>
            <input type="password" required value={confirm} onChange={e => setConfirm(e.target.value)} placeholder="••••••••" {...fieldProps()} />
          </div>

          {error && <div style={S.errorBox}>{error}</div>}

          <button type="submit" disabled={loading} style={{ ...S.btn, opacity: loading ? 0.6 : 1 }}>
            {loading ? 'Création…' : 'Créer mon compte'}
          </button>
        </form>

        <div style={S.altText}>
          Déjà un compte ?{' '}
          <Link to="/login" style={{ color: 'var(--color-accent-soft)' }}>Se connecter</Link>
        </div>
      </div>
    </div>
  )
}
