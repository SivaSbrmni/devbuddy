import { useNavigate } from 'react-router-dom'
import Icon from '../Icon'
import type { SessionListItem } from '../../api/sessions'

const STATUS_DOT: Record<string, string> = {
  queued: '#94a3b8',
  planning: '#818cf8',
  running: '#34d399',
  paused: '#fbbf24',
  completed: '#34d399',
  failed: '#ef4444',
  terminated: '#94a3b8',
}

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

interface Props {
  sessions: SessionListItem[]
  activeSessionId?: string
  loading?: boolean
  compact?: boolean
  onSelect?: (sessionId: string) => void
}

export default function SessionList({
  sessions,
  activeSessionId,
  loading,
  compact,
  onSelect,
}: Props) {
  const navigate = useNavigate()

  const openSession = (id: string) => {
    if (onSelect) {
      onSelect(id)
    } else {
      navigate(`/app/session/${id}`)
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: compact ? '4px 0' : '8px 12px' }}>
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="db-skeleton" style={{ height: compact ? 36 : 44, borderRadius: 8 }} />
        ))}
      </div>
    )
  }

  if (sessions.length === 0) {
    return (
      <div style={{
        padding: compact ? '12px 0' : '20px 12px',
        textAlign: 'center',
        color: 'var(--text-faint)',
        fontSize: 12,
      }}>
        <Icon name="terminal" size={18} style={{ opacity: 0.4, marginBottom: 6 }} />
        <div>No agent sessions yet</div>
        {!compact && (
          <div style={{ marginTop: 4, fontSize: 11 }}>Start a task with a repo to launch a session</div>
        )}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {sessions.map(session => {
        const isActive = session.id === activeSessionId
        const dot = STATUS_DOT[session.status] || STATUS_DOT.queued
        const isLive = ['queued', 'planning', 'running'].includes(session.status)

        return (
          <button
            key={session.id}
            type="button"
            onClick={() => openSession(session.id)}
            className="db-btn db-focus"
            style={{
              width: '100%',
              padding: compact ? '8px 10px' : '10px 12px',
              borderRadius: 'var(--radius-md)',
              background: isActive ? 'rgba(99,102,241,0.12)' : 'transparent',
              border: isActive ? '1px solid rgba(99,102,241,0.25)' : '1px solid transparent',
              color: 'var(--text)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'flex-start',
              gap: 10,
              textAlign: 'left',
              transition: 'all var(--transition-fast)',
            }}
            onMouseEnter={e => {
              if (!isActive) e.currentTarget.style.background = 'rgba(255,255,255,0.04)'
            }}
            onMouseLeave={e => {
              if (!isActive) e.currentTarget.style.background = 'transparent'
            }}
          >
            <span style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: dot,
              marginTop: 5,
              flexShrink: 0,
              boxShadow: isLive ? `0 0 8px ${dot}` : 'none',
              animation: isLive ? 'pulse 1.5s ease-in-out infinite' : 'none',
            }} />
            <span style={{ flex: 1, minWidth: 0 }}>
              <span style={{
                display: 'block',
                fontSize: 13,
                fontWeight: isActive ? 600 : 500,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}>
                {session.title}
              </span>
              <span style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                marginTop: 2,
                fontSize: 11,
                color: 'var(--text-faint)',
              }}>
                <span style={{ textTransform: 'capitalize' }}>{session.status}</span>
                <span>·</span>
                <span>{formatRelativeTime(session.updated_at)}</span>
                {session.pr_url && (
                  <>
                    <span>·</span>
                    <Icon name="pr" size={10} />
                  </>
                )}
              </span>
            </span>
          </button>
        )
      })}
    </div>
  )
}
