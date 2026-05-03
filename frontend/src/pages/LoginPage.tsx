import { useState, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'

const S = {
  page: {
    display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center',
    background: '#111111', padding: '24px',
  } satisfies React.CSSProperties,
  card: {
    width: '100%', maxWidth: 400,
    background: '#1A1A1A', border: '1px solid #2E2E2E', borderRadius: 16,
    padding: '44px 40px',
    boxShadow: '0 24px 64px rgba(0,0,0,0.6), 0 0 40px rgba(16,53,192,0.3)',
  } satisfies React.CSSProperties,
  logoWrap: { textAlign: 'center', marginBottom: 32 } satisfies React.CSSProperties,
  logoMark: {
    width: 52, height: 52, borderRadius: 12, background: '#1035C0',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    margin: '0 auto 14px',
    fontFamily: "'Orbitron', sans-serif", fontSize: 20, fontWeight: 700, color: '#fff',
    boxShadow: '0 0 24px rgba(16,53,192,0.4)',
  } satisfies React.CSSProperties,
  logoName: {
    fontFamily: "'Orbitron', sans-serif", fontSize: 15, fontWeight: 600,
    letterSpacing: '2.5px', color: '#EBEBEB',
  } satisfies React.CSSProperties,
  logoTagline: { fontSize: 12, color: '#888888', marginTop: 6, letterSpacing: '0.3px' } satisfies React.CSSProperties,
  successBanner: {
    background: 'rgba(34,197,94,0.12)', border: '1px solid rgba(34,197,94,0.25)',
    borderRadius: 8, padding: '10px 14px', marginBottom: 20,
    fontSize: 13, color: '#4ade80',
  } satisfies React.CSSProperties,
  title: { fontSize: 20, fontWeight: 600, color: '#EBEBEB', marginBottom: 6 } satisfies React.CSSProperties,
  subtitle: { fontSize: 13, color: '#888888', marginBottom: 28 } satisfies React.CSSProperties,
  fieldWrap: { marginBottom: 16 } satisfies React.CSSProperties,
  label: {
    display: 'block', fontSize: 11, fontWeight: 600,
    letterSpacing: '0.6px', textTransform: 'uppercase' as const,
    color: '#888888', marginBottom: 8,
  } satisfies React.CSSProperties,
  input: {
    width: '100%', background: '#181818', border: '1px solid #2E2E2E',
    borderRadius: 10, padding: '12px 14px', color: '#EBEBEB',
    fontSize: 14, outline: 'none', transition: 'border-color 0.15s, box-shadow 0.15s',
    boxSizing: 'border-box' as const,
  } satisfies React.CSSProperties,
  errorBox: {
    background: 'rgba(255,59,92,0.12)', border: '1px solid rgba(255,59,92,0.25)',
    borderRadius: 8, padding: '10px 14px', marginBottom: 16,
    fontSize: 13, color: '#FF3B5C',
  } satisfies React.CSSProperties,
  btn: {
    width: '100%', background: '#1035C0', border: 'none', borderRadius: 10,
    padding: '13px', color: '#fff', fontSize: 14, fontWeight: 600,
    letterSpacing: '0.3px', cursor: 'pointer', transition: 'all 0.15s',
    boxShadow: '0 0 16px rgba(16,53,192,0.3)', marginTop: 8,
  } satisfies React.CSSProperties,
  altText: { textAlign: 'center' as const, marginTop: 24, fontSize: 13, color: '#888888' } satisfies React.CSSProperties,
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
      e.currentTarget.style.borderColor = 'rgba(16,53,192,0.5)'
      e.currentTarget.style.boxShadow = '0 0 0 3px rgba(16,53,192,0.08)'
    },
    onBlur: (e: React.FocusEvent<HTMLInputElement>) => {
      e.currentTarget.style.borderColor = '#2E2E2E'
      e.currentTarget.style.boxShadow = 'none'
    },
  }

  return (
    <div style={S.page}>
      <div style={S.card}>
        <div style={S.logoWrap}>
          <div style={S.logoMark}>G</div>
          <div style={S.logoName}>GOLAI</div>
          <div style={S.logoTagline}>Ton IA pour explorer le jeu vidéo</div>
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
            onMouseEnter={e => { e.currentTarget.style.background = '#1E45D0' }}
            onMouseLeave={e => { e.currentTarget.style.background = '#1035C0' }}
          >
            {loading ? 'Connexion…' : 'Se connecter'}
          </button>
        </form>

        <div style={S.altText}>
          Pas encore de compte ?{' '}
          <Link to="/register" style={{ color: '#5B7EFF' }}>S'inscrire</Link>
        </div>
      </div>
    </div>
  )
}
