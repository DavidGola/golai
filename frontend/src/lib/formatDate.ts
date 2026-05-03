export function formatRelativeDate(isoDate: string): string {
  const date = new Date(isoDate)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const hours = diff / (1000 * 60 * 60)

  if (hours < 1) return 'Il y a moins d\'1 h'
  if (hours < 24) return `Il y a ${Math.floor(hours)} h`
  if (hours < 48) return 'Hier'

  return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })
}
