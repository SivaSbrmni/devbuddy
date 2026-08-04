import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useSession } from '../hooks/useSession'
import SessionHeader from '../components/session/SessionHeader'
import ProgressPanel from '../components/session/ProgressPanel'
import ShellPanel from '../components/session/ShellPanel'
import FilesPanel from '../components/session/FilesPanel'
import Icon from '../components/Icon'

type Tab = 'progress' | 'shell' | 'files'

const TABS: { id: Tab; label: string; icon: 'list' | 'terminal' | 'file' }[] = [
  { id: 'progress', label: 'Progress', icon: 'list' },
  { id: 'shell', label: 'Shell', icon: 'terminal' },
  { id: 'files', label: 'Files', icon: 'file' },
]

export default function SessionWorkspace() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('progress')
  const [terminating, setTerminating] = useState(false)

  const {
    session,
    loading,
    error,
    events,
    shellEntries,
    fileChanges,
    thinkingLog,
    plan,
    prUrl,
    devboxMessage,
    streamingContent,
    terminate,
  } = useSession(sessionId || '')

  const handleTerminate = async () => {
    setTerminating(true)
    try {
      await terminate()
    } finally {
      setTerminating(false)
    }
  }

  if (!sessionId) {
    return null
  }

  if (loading && !session) {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="db-skeleton" style={{ width: 48, height: 48, borderRadius: 14, margin: '0 auto 16px' }} />
          <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>Loading session…</div>
        </div>
      </div>
    )
  }

  const repo = session?.repository_owner && session?.repository_name
    ? `${session.repository_owner}/${session.repository_name}`
    : null

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--bg)',
      display: 'flex',
      flexDirection: 'column',
    }}>
      <SessionHeader
        title={session?.title || 'Session'}
        status={session?.status || 'queued'}
        repo={repo}
        onBack={() => navigate('/app')}
        onTerminate={handleTerminate}
        terminating={terminating}
      />

      {error && (
        <div style={{
          margin: '12px 20px 0',
          padding: '12px 16px',
          borderRadius: 10,
          background: 'rgba(239,68,68,0.1)',
          border: '1px solid rgba(239,68,68,0.25)',
          color: '#fca5a5',
          fontSize: 13,
        }}>
          {error}
        </div>
      )}

      {(prUrl || session?.pr_url) && (
        <div style={{
          margin: '12px 20px 0',
          padding: '14px 18px',
          borderRadius: 12,
          background: 'linear-gradient(135deg, rgba(52,211,153,0.1) 0%, rgba(99,102,241,0.08) 100%)',
          border: '1px solid rgba(52,211,153,0.25)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Icon name="pr" size={18} />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>Pull request ready</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Review DevBuddy's changes on GitHub</div>
            </div>
          </div>
          <a
            href={prUrl || session?.pr_url || '#'}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              padding: '8px 16px',
              borderRadius: 10,
              background: 'var(--accent)',
              color: '#fff',
              fontSize: 13,
              fontWeight: 600,
              textDecoration: 'none',
            }}
          >
            View PR
          </a>
        </div>
      )}

      <div style={{
        flex: 1,
        display: 'grid',
        gridTemplateColumns: 'minmax(280px, 340px) 1fr',
        gap: 0,
        minHeight: 0,
        marginTop: 12,
      }}>
        {/* Left: prompt + thinking stream */}
        <aside style={{
          borderRight: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--bg-elevated)',
        }}>
          <div style={{ padding: '16px 18px', borderBottom: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
              Your task
            </div>
            <div style={{ fontSize: 14, color: 'var(--text)', lineHeight: 1.6 }}>
              {session?.prompt}
            </div>
          </div>

          <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
              Agent output
            </div>
            {streamingContent ? (
              <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
                {streamingContent}
                <span style={{ animation: 'pulse 1s infinite' }}>▋</span>
              </div>
            ) : thinkingLog.length > 0 ? (
              thinkingLog.map(entry => (
                <div key={entry.id} style={{ marginBottom: 14, fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6 }}>
                  {entry.phase && (
                    <span style={{ fontSize: 10, color: 'var(--accent-hover)', fontWeight: 600, textTransform: 'uppercase' }}>
                      {entry.phase} ·{' '}
                    </span>
                  )}
                  {entry.content}
                </div>
              ))
            ) : (
              <div style={{ fontSize: 13, color: 'var(--text-faint)', fontStyle: 'italic' }}>
                DevBuddy is working on your task…
              </div>
            )}
          </div>
        </aside>

        {/* Right: tabbed workspace */}
        <main style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <nav style={{
            display: 'flex',
            gap: 4,
            padding: '8px 12px',
            borderBottom: '1px solid var(--border-subtle)',
            background: 'var(--bg-elevated)',
          }}>
            {TABS.map(t => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '8px 14px',
                  borderRadius: 8,
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: 500,
                  background: tab === t.id ? 'var(--accent-glow)' : 'transparent',
                  color: tab === t.id ? 'var(--accent-hover)' : 'var(--text-muted)',
                  borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
                }}
              >
                <Icon name={t.icon} size={14} />
                {t.label}
                {t.id === 'shell' && shellEntries.length > 0 && (
                  <span style={{ fontSize: 10, background: 'var(--bg-card)', padding: '1px 6px', borderRadius: 999 }}>
                    {shellEntries.length}
                  </span>
                )}
                {t.id === 'files' && fileChanges.length > 0 && (
                  <span style={{ fontSize: 10, background: 'var(--bg-card)', padding: '1px 6px', borderRadius: 999 }}>
                    {fileChanges.length}
                  </span>
                )}
              </button>
            ))}
          </nav>

          <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
            {tab === 'progress' && (
              <ProgressPanel plan={plan} devboxMessage={devboxMessage} events={events} />
            )}
            {tab === 'shell' && <ShellPanel entries={shellEntries} />}
            {tab === 'files' && <FilesPanel files={fileChanges} />}
          </div>
        </main>
      </div>
    </div>
  )
}
