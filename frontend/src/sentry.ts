import * as Sentry from '@sentry/react'

const sentryEnabled = import.meta.env.VITE_SENTRY_ENABLED === 'true'
const sentryDsn = import.meta.env.VITE_SENTRY_DSN

if (sentryEnabled && sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    environment: import.meta.env.VITE_SENTRY_ENVIRONMENT || 'development',
    release: import.meta.env.VITE_SENTRY_RELEASE || undefined,
    sendDefaultPii: false,
    tracesSampleRate: 0,
  })
}

export { Sentry }
