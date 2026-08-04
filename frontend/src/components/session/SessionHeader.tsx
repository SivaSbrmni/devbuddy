import Icon from '../Icon'

const STATUS_STYLES: Record<string, { color: string; bg: string; label: string }> = {
  queued: { color: '#94a3b8', bg: 'rgba(148,163,184,0.12)', label: 'Queued' },
  planning: { color: '#818cf8', bg: 'rgba(129,140,248,0.15)', label: 'Planning' },
  running: { color: '#34d399', bg: 'rgba(52,211,153,0.12)', label: 'Running' },
  paused: { color: '#fbbf24', bg: 'rgba(251,191,36,0.12)', label: 'Paused' },
  completed: { color: '#34d399', bg: 'rgba(52,211,153,0.12)', label: 'Completed' },
  failed: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)', label: 'Failed' },
  terminated: { color: '#94a3b8', bg: 'rgba(148,163,184,0.12)', label: 'Terminated' },
}

interface Props {
  title: string
  status: string
  repo?: string | null
  githubRunUrl?: string | null
  onBack: () => void
  onTerminate: () => void
  onToggleSessions?: () => void
  terminating?: boolean
}

export default function SessionHeader({
  title,
  status,
  repo,
  githubRunUrl,
  onBack,
  onTerminate,
  onToggleSessions,
  terminating,
}: Props) {
  const s = STATUS_STYLES[status] || STATUS_STYLES.queued
  const isActive = status === 'running' || status === 'planning' || status === 'queued'

  return (
    <header style={{
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      padding: '14px 20px',
      borderBottom: '1px solid var(--border-subtle)',
      background: 'linear-gradient(180deg, rgba(17,19,24,0.98) 0%, rgba(13,15,20,0.95) 100%)',
      backdropFilter: 'blur(12px)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <button
          onClick={onBack}
          style={{
            background: 'transparent',
            border: '1px solid var(--border)',
            color: 'var(--text-muted)',
            padding: '8px 10px',
            borderRadius: 10,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            cursor: 'pointer',
          }}
        >
          <Icon name="chevron-right" size={14} style={{ transform: 'rotate(180deg)' }} />
        </button>
        {onToggleSessions && (
          <button
            onClick={onToggleSessions}
            className="session-mobile-only"
            aria-label="Session history"
            style={{
              background: 'transparent',
              border: '1px solid var(--border)',
              color: 'var(--text-muted)',
              padding: '8px 10px',
              borderRadius: 10,
              cursor: 'pointer',
            }}
          >
            <Icon name="list" size={14} />
          </button>
        )}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 15,
          fontWeight: 600,
          color: 'var(--text)',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}>
          {title}
        </div>
        {repo && (
          <div style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 2, display: 'flex', alignItems: 'center', gap: 4 }}>
            <Icon name="repo" size={11} />
            {repo}
          </div>
        )}
      </div>

      <span style={{
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        color: s.color,
        background: s.bg,
        padding: '5px 10px',
        borderRadius: 999,
        display: 'flex',
        alignItems: 'center',
        gap: 6,
      }}>
        {isActive && (
          <span style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: s.color,
            animation: 'pulse 1.5s ease-in-out infinite',
          }} />
        )}
        {s.label}
      </span>

      {githubRunUrl && (
        <a
          href={githubRunUrl}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '7px 12px',
            borderRadius: 10,
            border: '1px solid var(--border)',
            color: 'var(--text-muted)',
            fontSize: 12,
            textDecoration: 'none',
          }}
        >
          <Icon name="git" size={14} />
          <span className="session-desktop-only">Workflow</span>
        </a>
      )}

      {isActive && (
        <button
          onClick={onTerminate}
          disabled={terminating}
          style={{
            background: 'rgba(239,68,68,0.1)',
            border: '1px solid rgba(239,68,68,0.3)',
            color: '#fca5a5',
            padding: '8px 14px',
            borderRadius: 10,
            fontSize: 13,
            fontWeight: 500,
            cursor: terminating ? 'not-allowed' : 'pointer',
            opacity: terminating ? 0.6 : 1,
          }}
        >
          {terminating ? 'Stopping…' : 'Stop'}
        </button>
      )}
    </header>
  )
}
