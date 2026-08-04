import type { FileChange } from '../../hooks/useSession'
import Icon from '../Icon'

interface Props {
  files: FileChange[]
}

export default function FilesPanel({ files }: Props) {
  return (
    <div style={{ padding: 16, height: '100%', overflow: 'auto' }}>
      {files.length === 0 ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-faint)' }}>
          <Icon name="edit" size={24} />
          <div style={{ fontSize: 13, marginTop: 12 }}>No file changes yet</div>
          <div style={{ fontSize: 12, marginTop: 4 }}>Modified files will appear here with diffs</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {files.map((f, i) => (
            <div
              key={`${f.path}-${i}`}
              style={{
                borderRadius: 10,
                border: '1px solid var(--border)',
                background: 'var(--bg-card)',
                overflow: 'hidden',
              }}
            >
              <div style={{
                padding: '10px 14px',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                borderBottom: f.diff ? '1px solid var(--border-subtle)' : 'none',
              }}>
                <span style={{
                  fontSize: 10,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  color: f.action === 'create' ? 'var(--success)' : 'var(--accent-hover)',
                  background: f.action === 'create' ? 'rgba(52,211,153,0.12)' : 'var(--accent-glow)',
                  padding: '2px 6px',
                  borderRadius: 4,
                }}>
                  {f.action}
                </span>
                <span style={{ fontSize: 13, color: 'var(--text)', fontFamily: 'monospace' }}>{f.path}</span>
              </div>
              {f.diff && (
                <pre style={{
                  margin: 0,
                  padding: 12,
                  fontSize: 11,
                  lineHeight: 1.5,
                  color: 'var(--text-dim)',
                  background: '#0a0c10',
                  overflow: 'auto',
                  maxHeight: 200,
                }}>
                  {f.diff}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
