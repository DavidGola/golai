import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { login as apiLogin, register as apiRegister, logout as apiLogout, getMe } from '@/api/auth'
import { tokenStorage } from '@/lib/tokenStorage'
import { queryClient } from '@/lib/queryClient'
import type { UserProfile } from '@/types/auth'

interface AuthContextValue {
  user: UserProfile | null
  isLoading: boolean
  login: (identifier: string, password: string) => Promise<void>
  register: (email: string, password: string, username: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const token = tokenStorage.get()
    if (!token) {
      setIsLoading(false)
      return
    }
    getMe()
      .then(setUser)
      .catch(() => tokenStorage.clear())
      .finally(() => setIsLoading(false))
  }, [])

  async function login(identifier: string, password: string) {
    const { access_token } = await apiLogin(identifier, password)
    tokenStorage.set(access_token)
    const profile = await getMe()
    setUser(profile)
  }

  async function register(email: string, password: string, username: string) {
    await apiRegister(email, password, username)
  }

  async function logout() {
    try { await apiLogout() } catch { /* ignore */ }
    tokenStorage.clear()
    queryClient.clear()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuthContext must be used inside AuthProvider')
  return ctx
}
