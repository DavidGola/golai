import { useState, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'

const S = {
  page: {
    display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center',
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
  logoTagline: { fontSize: 12, color: 'var(--color-subtle)', marginTop: 6, letterSpacing: '0.3px' } satisfies React.CSSProperties,
  successBanner: {
    background: 'var(--color-success-dim)', border: '1px solid var(--color-success-ring)',
    borderRadius: 8, padding: '10px 14px', marginBottom: 20,
    fontSize: 13, color: 'var(--color-success)',
  } satisfies React.CSSProperties,
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
    fontSize: 14, outline: 'none', transition: 'border-color 0.15s, box-shadow 0.15s',
    boxSizing: 'border-box' as const,
  } satisfies React.CSSProperties,
  errorBox: {
    background: 'var(--color-danger-dim)', border: '1px solid var(--color-danger-ring)',
    borderRadius: 8, padding: '10px 14px', marginBottom: 16,
    fontSize: 13, color: 'var(--color-danger)',
  } satisfies React.CSSProperties,
  btn: {
    width: '100%', background: 'var(--color-accent)', border: 'none', borderRadius: 10,
    padding: '13px', color: '#fff', fontSize: 14, fontWeight: 600,
    letterSpacing: '0.3px', cursor: 'pointer', transition: 'all 0.15s',
    boxShadow: '0 0 16px var(--color-accent-glow)', marginTop: 8,
  } satisfies React.CSSProperties,
  altText: { textAlign: 'center' as const, marginTop: 24, fontSize: 13, color: 'var(--color-subtle)' } satisfies React.CSSProperties,
}

interface LocationState {
  justRegistered?: boolean
  email?: string
}

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const state = location.state as LocationState | null

  const [identifier, setIdentifier] = useState(state?.email ?? '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showSuccess, setShowSuccess] = useState(!!state?.justRegistered)

  useEffect(() => {
    if (!showSuccess) return
    const t = setTimeout(() => setShowSuccess(false), 5000)
    return () => clearTimeout(t)
  }, [showSuccess])

  async function submit() {
    setError('')
    setLoading(true)
    try {
      await login(identifier, password)
      navigate('/', { replace: true })
    } catch {
      setError('Identifiant ou mot de passe incorrect.')
    } finally {
      setLoading(false)
    }
  }

  const focusProps = {
    onFocus: (e: React.FocusEvent<HTMLInputElement>) => {
      e.currentTarget.style.borderColor = 'var(--color-accent-focus)'
      e.currentTarget.style.boxShadow = '0 0 0 3px var(--color-accent-focus-soft)'
    },
    onBlur: (e: React.FocusEvent<HTMLInputElement>) => {
      e.currentTarget.style.borderColor = 'var(--color-separator)'
      e.currentTarget.style.boxShadow = 'none'
    },
  }

  return (
    <div style={S.page}>
      <div style={S.card}>
        <div style={S.logoWrap}>
          <div style={S.logoMark}>G</div>
          <div style={S.logoName}>GOLAI</div>
          <div style={S.logoTagline}>Recommandation de jeux vidéo</div>
        </div>

        {showSuccess && (
          <div style={S.successBanner}>
            Compte créé avec succès — connecte-toi pour commencer !
          </div>
        )}

        <div style={S.title}>Connexion</div>
        <div style={S.subtitle}>Bienvenue de retour.</div>

        <form onSubmit={e => { e.preventDefault(); void submit() }}>
          <div style={S.fieldWrap}>
            <label style={S.label}>Pseudo ou email</label>
            <input
              type="text" required value={identifier}
              onChange={e => setIdentifier(e.target.value)}
              placeholder="TonPseudo ou vous@exemple.com"
              style={S.input}
              {...focusProps}
            />
          </div>

          <div style={S.fieldWrap}>
            <label style={S.label}>Mot de passe</label>
            <input
              type="password" required value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              style={S.input}
              {...focusProps}
            />
          </div>

          {error && <div style={S.errorBox}>{error}</div>}

          <button
            type="submit" disabled={loading} style={{ ...S.btn, opacity: loading ? 0.6 : 1 }}
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--color-accent-hover)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'var(--color-accent)' }}
          >
            {loading ? 'Connexion…' : 'Se connecter'}
          </button>
        </form>

        <div style={S.altText}>
          Pas encore de compte ?{' '}
          <Link to="/register" style={{ color: 'var(--color-accent-soft)' }}>S'inscrire</Link>
        </div>
      </div>
    </div>
  )
}
