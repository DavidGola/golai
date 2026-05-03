export function SentryTestButton() {
  if (import.meta.env.VITE_SENTRY_ENABLED !== 'true') return null

  return (
    <button
      type="button"
      onClick={() => {
        throw new Error('GolAi frontend browser Sentry test')
      }}
      style={{
        position: 'fixed',
        right: 16,
        bottom: 16,
        zIndex: 9999,
        padding: '10px 12px',
        borderRadius: 6,
        border: '1px solid #ef4444',
        background: '#111111',
        color: '#ffffff',
        cursor: 'pointer',
      }}
    >
      Test Sentry
    </button>
  )
}
