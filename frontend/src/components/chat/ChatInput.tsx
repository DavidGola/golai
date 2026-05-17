import { useState, useRef } from 'react'

interface Props {
  onSend: (content: string) => void
  disabled?: boolean
  model?: string
}

export default function ChatInput({ onSend, disabled, model }: Props) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function handleSend() {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function handleInput() {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  return (
    <div style={{
      flexShrink: 0, borderTop: '1px solid var(--color-separator)', background: 'var(--color-base)',
      padding: '12px 20px 16px',
    }}>
      <div style={{ position: 'relative', maxWidth: 680, margin: '0 auto' }}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={e => handleKeyDown(e as unknown as KeyboardEvent)}
          onInput={handleInput}
          placeholder="Parle de jeu vidéo…"
          rows={1}
          disabled={disabled}
          style={{
            display: 'block', width: '100%', resize: 'none',
            borderRadius: 16,
            border: '1px solid var(--color-separator)',
            background: 'var(--color-input-bg)',
            padding: '14px 52px 14px 18px',
            fontSize: 14, lineHeight: 1.5,
            color: 'var(--color-content)',
            outline: 'none',
            minHeight: 52, maxHeight: 160,
            boxSizing: 'border-box',
            fontFamily: 'inherit',
            opacity: disabled ? 0.5 : 1,
            transition: 'border-color 0.15s, box-shadow 0.15s',
          }}
          onFocus={e => {
            e.currentTarget.style.borderColor = 'var(--color-accent-focus)'
            e.currentTarget.style.boxShadow = '0 0 0 3px var(--color-accent-focus-soft)'
          }}
          onBlur={e => {
            e.currentTarget.style.borderColor = 'var(--color-separator)'
            e.currentTarget.style.boxShadow = 'none'
          }}
        />
        <button
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          style={{
            position: 'absolute', top: '50%', transform: 'translateY(-50%)', right: 12,
            width: 32, height: 32,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            borderRadius: '50%',
            background: 'var(--color-accent)',
            color: '#fff',
            border: 'none', cursor: 'pointer',
            boxShadow: '0 0 12px var(--color-accent-shine)',
            transition: 'all 0.15s',
            opacity: (disabled || !value.trim()) ? 0.35 : 1,
          }}
          aria-label="Envoyer"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M8 13V3M3 8l5-5 5 5"/>
          </svg>
        </button>
      </div>
      <div style={{
        marginTop: 8,
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        gap: '4px 10px',
        fontSize: 11,
        color: 'var(--color-ghost)',
      }}>
        {model && <span>Modèle : {model}</span>}
        <span>Entrée pour envoyer · Maj+Entrée pour un saut de ligne</span>
      </div>
    </div>
  )
}
