import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'

const S = {
  page: {
    display: 'flex', minHeight: '100%', alignItems: 'center', justifyContent: 'center',
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
  logoTagline: { fontSize: 12, color: '#888888', marginTop: 6 } satisfies React.CSSProperties,
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
    fontSize: 14, outline: 'none', boxSizing: 'border-box' as const,
  } satisfies React.CSSProperties,
  errorBox: {
    background: 'rgba(255,59,92,0.12)', border: '1px solid rgba(255,59,92,0.25)',
    borderRadius: 8, padding: '10px 14px', marginBottom: 16,
    fontSize: 13, color: '#FF3B5C',
  } satisfies React.CSSProperties,
  btn: {
    width: '100%', background: '#1035C0', border: 'none', borderRadius: 10,
    padding: '13px', color: '#fff', fontSize: 14, fontWeight: 600,
    cursor: 'pointer', boxShadow: '0 0 16px rgba(16,53,192,0.3)', marginTop: 8,
  } satisfies React.CSSProperties,
  altText: { textAlign: 'center' as const, marginTop: 24, fontSize: 13, color: '#888888' } satisfies React.CSSProperties,
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
      e.currentTarget.style.borderColor = 'rgba(16,53,192,0.5)'
      e.currentTarget.style.boxShadow = '0 0 0 3px rgba(16,53,192,0.08)'
      onFocus?.()
    },
    onBlur: (e: React.FocusEvent<HTMLInputElement>) => {
      e.currentTarget.style.borderColor = '#2E2E2E'
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
          <Link to="/login" style={{ color: '#5B7EFF' }}>Se connecter</Link>
        </div>
      </div>
    </div>
  )
}
