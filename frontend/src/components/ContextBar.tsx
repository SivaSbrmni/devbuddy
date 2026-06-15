import Icon from './Icon'

interface ContextFile {
  path: string
  status: 'modified' | 'new' | 'error' | 'clean'
}

interface ContextBarProps {
  project?: string
  branch?: string
  files?: ContextFile[]
  lastTopic?: string
  onFileClick?: (path: string) => void
}

const statusColors: Record<string, string> = {
  modified: '#fbbf24',
  new: '#34d399',
  error: '#ef4444',
  clean: '#6b7280',
}

export default function ContextBar({ project, branch, files, lastTopic, onFileClick }: ContextBarProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        padding: '6px 16px',
        background: 'var(--bg-card)',
        borderBottom: '1px solid var(--border-subtle)',
        fontSize: 12,
        color: 'var(--text-dim)',
        flexShrink: 0,
        overflow: 'hidden',
      }}
    >
      {/* Project */}
      {project && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          <Icon name="folder" size={12} style={{ color: 'var(--accent-hover)' }} />
          <span style={{ color: 'var(--text)', fontWeight: 600 }}>{project}</span>
          {branch && (
            <span style={{ background: 'var(--bg-elevated)', padding: '1px 6px', borderRadius: 'var(--radius-sm)', fontSize: 11, color: 'var(--text-muted)' }}>
              {branch}
            </span>
          )}
        </div>
      )}

      {/* Divider */}
      <div style={{ width: 1, height: 16, background: 'var(--border-subtle)', flexShrink: 0 }} />

      {/* Recent files */}
      {files && files.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0, overflow: 'hidden' }}>
          <span style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-faint)' }}>Files</span>
          <div style={{ display: 'flex', gap: 6, overflow: 'hidden' }}>
            {files.slice(0, 4).map(f => (
              <button
                key={f.path}
                onClick={() => onFileClick?.(f.path)}
                className="db-btn"
                title={f.path}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '2px 8px',
                  fontSize: 11,
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  transition: 'all var(--transition-fast)',
                  flexShrink: 0,
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = 'var(--accent)'
                  e.currentTarget.style.color = 'var(--text)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'var(--border)'
                  e.currentTarget.style.color = 'var(--text-muted)'
                }}
              >
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: statusColors[f.status] }} />
                {f.path.split('/').pop()}
              </button>
            ))}
            {files.length > 4 && (
              <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>+{files.length - 4}</span>
            )}
          </div>
        </div>
      )}

      {/* Last topic */}
      {lastTopic && (
        <>
          <div style={{ width: 1, height: 16, background: 'var(--border-subtle)', flexShrink: 0 }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0, overflow: 'hidden' }}>
            <Icon name="brain" size={12} style={{ color: 'var(--text-faint)' }} />
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 200 }}>
              Last: {lastTopic}
            </span>
          </div>
        </>
      )}

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Context hint */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--text-faint)', fontSize: 11, flexShrink: 0 }}>
        <Icon name="command" size={10} />
        <span>Type @ to reference files</span>
      </div>
    </div>
  )
}
