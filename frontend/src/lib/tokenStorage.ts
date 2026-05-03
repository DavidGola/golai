const KEY = 'golai_token'

export const tokenStorage = {
  get: (): string | null => localStorage.getItem(KEY),
  set: (token: string): void => { localStorage.setItem(KEY, token) },
  clear: (): void => { localStorage.removeItem(KEY) },
}
