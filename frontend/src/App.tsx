import { Routes, Route } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'
import ProtectedRoute from '@/auth/ProtectedRoute'
import LoginPage from '@/pages/LoginPage'
import RegisterPage from '@/pages/RegisterPage'
import ChatPage from '@/pages/ChatPage'
import ProfilePage from '@/pages/ProfilePage'
import NotFoundPage from '@/pages/NotFoundPage'
import AboutPage from '@/pages/AboutPage'

export default function App() {
  const { isLoading } = useAuth()

  if (isLoading) {
    return (
      <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', background: '#111111' }}>
        <div style={{
          width: 24, height: 24,
          border: '2px solid #1035C0',
          borderTopColor: 'transparent',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
        }} />
      </div>
    )
  }

  return (
    <Routes>
      {/* Chat : page principale, accessible sans compte */}
      <Route path="/" element={<ChatPage />} />
      <Route path="/chat" element={<ChatPage />} />
      <Route path="/chat/:id" element={<ChatPage />} />

      {/* Auth */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* Profil : requiert un compte */}
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        }
      />

      <Route path="/about" element={<AboutPage />} />

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
