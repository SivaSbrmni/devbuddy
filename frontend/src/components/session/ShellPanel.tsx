import type { ShellEntry } from '../../hooks/useSession'

interface Props {
  entries: ShellEntry[]
}

export default function ShellPanel({ entries }: Props) {
  return (
    <div style={{
      height: '100%',
      overflow: 'auto',
      background: '#0a0c10',
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      fontSize: 12,
      lineHeight: 1.6,
    }}>
      {entries.length === 0 ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-faint)' }}>
          <div style={{ fontSize: 13, marginBottom: 8 }}>Terminal</div>
          <div style={{ fontSize: 12 }}>Commands will appear here as DevBuddy works</div>
        </div>
      ) : (
        entries.map((entry) => (
          <div key={entry.id} style={{ borderBottom: '1px solid #1a1d27' }}>
            <div style={{
              padding: '10px 16px',
              background: '#111318',
              color: '#818cf8',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}>
              <span style={{ color: '#34d399' }}>$</span>
              <span style={{ flex: 1 }}>{entry.command}</span>
              <span style={{
                fontSize: 10,
                color: entry.exitCode === 0 ? '#34d399' : '#ef4444',
              }}>
                exit {entry.exitCode}
              </span>
            </div>
            {entry.output && (
              <pre style={{
                margin: 0,
                padding: '12px 16px',
                color: '#b0b8c8',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}>
                {entry.output}
              </pre>
            )}
          </div>
        ))
      )}
    </div>
  )
}
