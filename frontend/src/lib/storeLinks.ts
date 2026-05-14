import type { StoreLink, StorePlatform } from '@/types/store'

export const STORE_LABEL: Record<StorePlatform, string> = {
  steam: 'Steam',
  playstation: 'PS Store',
  nintendo: 'Nintendo eShop',
  xbox: 'Xbox Store',
  epic: 'Epic Games',
  gog: 'GOG',
}

export function pickStoreLink(
  links: StoreLink[],
  preferred: StorePlatform | null | undefined,
): StoreLink | null {
  if (!links.length) return null
  if (preferred) {
    const match = links.find(l => l.platform === preferred)
    if (match) return match
  }
  return links[0] ?? null
}
