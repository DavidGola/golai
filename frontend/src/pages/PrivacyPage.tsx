import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useAuth } from '@/auth/useAuth'
import SidebarLeft from '@/components/layout/SidebarLeft'
import privacyContent from '@/content/privacy.md?raw'

export default function PrivacyPage() {
  const { user } = useAuth()

  return (
    <div className="flex h-full">
      {user && <SidebarLeft />}

      <main className="flex-1 overflow-y-auto px-6 py-10">
        <div className="mx-auto max-w-[720px]">
          {!user && (
            <a href="/" className="mb-8 block text-[13px] text-muted transition-colors hover:text-primary">
              ← Retour
            </a>
          )}
          <article className="prose">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {privacyContent}
            </ReactMarkdown>
          </article>
        </div>
      </main>
    </div>
  )
}
