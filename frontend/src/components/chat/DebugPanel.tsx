import { useState } from 'react'
import type { DebugEvent } from '@/hooks/useChatStream'

const STYLE_PRE: React.CSSProperties = {
  marginTop: 6,
  background: '#0A0A0A',
  border: '1px solid #1E1E1E',
  borderRadius: 6,
  padding: '8px 10px',
  fontSize: 12,
  fontFamily: 'monospace',
  color: '#777',
  overflow: 'auto',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-all',
}

function formatHeader(e: DebugEvent): string {
  const t = new Date(e.ts).toISOString().slice(11, 23)
  if (e.kind === 'tool_call') return `[${t}] → ${e.name}\n  args: ${e.args_preview}`
  if (e.kind === 'tool_result') {
    const dur = e.duration_ms != null ? ` (${e.duration_ms}ms)` : ''
    return `[${t}] ← ${e.name}${dur}`
  }
  if (e.kind === 'proposal') return `[${t}] ⊕ proposal ${e.action_type} #${e.proposal_id.slice(0, 8)}`
  return ''
}

function formatJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    return raw
  }
}

function DebugEventRow({ e }: { e: DebugEvent }) {
  const [expanded, setExpanded] = useState(false)
  const header = formatHeader(e)

  if (e.kind !== 'tool_result') {
    return <div style={{ marginBottom: 8 }}>{header}</div>
  }

  const isTruncated = e.result_preview.endsWith('…')
  const label = expanded ? '▾ result' : '▸ result'

  return (
    <div style={{ marginBottom: 8 }}>
      <div>{header}</div>
      <div style={{ marginTop: 2 }}>
        <button
          onClick={() => setExpanded(o => !o)}
          style={{
            fontSize: 11,
            fontFamily: 'monospace',
            background: 'transparent',
            border: 'none',
            color: '#555',
            cursor: 'pointer',
            padding: '0 0 0 2px',
          }}
        >
          {label}{isTruncated && !expanded ? ' (tronqué)' : ''}
        </button>
        {expanded && (
          <pre style={{ margin: '4px 0 0 0', color: '#999', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
            {formatJson(e.result_json)}
          </pre>
        )}
        {!expanded && (
          <span style={{ color: '#444', fontSize: 11 }}>  {e.result_preview}</span>
        )}
      </div>
    </div>
  )
}

export default function DebugPanel({ events }: { events: DebugEvent[] }) {
  const [open, setOpen] = useState(false)

  if (!import.meta.env.DEV || events.length === 0) return null

  return (
    <div style={{ marginTop: 10 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          fontSize: 12,
          fontFamily: 'monospace',
          background: 'transparent',
          border: '1px solid #2A2A2A',
          borderRadius: 4,
          color: '#555',
          padding: '2px 8px',
          cursor: 'pointer',
        }}
      >
        {open ? '▾' : '▸'} debug ({events.length} events)
      </button>
      {open && (
        <pre style={STYLE_PRE}>
          {events.map((e, i) => <DebugEventRow key={i} e={e} />)}
        </pre>
      )}
    </div>
  )
}
