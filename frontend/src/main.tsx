import { Sentry } from '@/sentry'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from '@/lib/queryClient'
import { AuthProvider } from '@/auth/AuthContext'
import App from '@/App'
import { SentryTestButton } from '@/components/SentryTestButton'
import './index.css'

const root = document.getElementById('root')
if (!root) throw new Error('Root element not found')

createRoot(root).render(
  <StrictMode>
    <Sentry.ErrorBoundary fallback={<div>Une erreur est survenue.</div>}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <App />
            <SentryTestButton />
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </Sentry.ErrorBoundary>
  </StrictMode>,
)
