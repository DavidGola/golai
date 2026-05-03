import { apiClient } from '@/lib/apiClient'
import { LoginResponseSchema, UserProfileSchema, type LoginResponse, type UserProfile } from '@/types/auth'

export async function login(identifier: string, password: string): Promise<LoginResponse> {
  const body = new URLSearchParams({ username: identifier, password })
  const res = await apiClient.post<unknown>('/auth/jwt/login', body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return LoginResponseSchema.parse(res.data)
}

export async function register(email: string, password: string, username: string): Promise<UserProfile> {
  const res = await apiClient.post<unknown>('/auth/register', { email, password, username })
  return UserProfileSchema.parse(res.data)
}

export async function logout(): Promise<void> {
  await apiClient.post('/auth/jwt/logout')
}

export async function getMe(): Promise<UserProfile> {
  const res = await apiClient.get<unknown>('/users/me')
  return UserProfileSchema.parse(res.data)
}
