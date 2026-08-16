import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useSession } from '../hooks/useSession'
import { useSessionList } from '../hooks/useSessionList'
import SessionHeader from '../components/session/SessionHeader'
import ProgressPanel from '../components/session/ProgressPanel'
import ShellPanel from '../components/session/ShellPanel'
import FilesPanel from '../components/session/FilesPanel'
import FollowUpComposer from '../components/session/FollowUpComposer'
import SessionList from '../components/session/SessionList'
import Icon from '../components/Icon'

type Tab = 'progress' | 'shell' | 'files'

const TABS: { id: Tab; label: string; icon: 'list' | 'terminal' | 'file' }[] = [
  { id: 'progress', label: 'Progress', icon: 'list' },
  { id: 'shell', label: 'Shell', icon: 'terminal' },
  { id: 'files', label: 'Files', icon: 'file' },
]

function useIsMobile(breakpoint = 900) {
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth < breakpoint : false
  )

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < breakpoint)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [breakpoint])

  return isMobile
}

export default function SessionWorkspace() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const isMobile = useIsMobile()
  const [tab, setTab] = useState<Tab>('progress')
  const [terminating, setTerminating] = useState(false)
  const [sessionsOpen, setSessionsOpen] = useState(false)
  const [showTaskPanel, setShowTaskPanel] = useState(true)

  const { sessions, loading: sessionsLoading } = useSessionList()
  const {
    session,
    loading,
    error,
    notFound,
    events,
    shellEntries,
    fileChanges,
    thinkingLog,
    plan,
    prUrl,
    devboxMessage,
    streamingContent,
    terminate,
    sendMessage,
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
      <div className="session-workspace" style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="db-skeleton" style={{ width: 48, height: 48, borderRadius: 14, margin: '0 auto 16px' }} />
          <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>Loading session…</div>
        </div>
      </div>
    )
  }

  if (notFound) {
    return (
      <div className="session-workspace" style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
        <div style={{ textAlign: 'center', maxWidth: 360 }}>
          <Icon name="warning" size={32} style={{ color: 'var(--text-faint)', marginBottom: 16 }} />
          <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>Session not found</div>
          <div style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 20 }}>
            This session may have been deleted or you may not have access.
          </div>
          <button
            type="button"
            onClick={() => navigate('/app')}
            style={{
              padding: '10px 18px',
              borderRadius: 10,
              border: '1px solid var(--border)',
              background: 'var(--bg-card)',
              color: 'var(--text)',
              cursor: 'pointer',
            }}
          >
            Back to workspace
          </button>
        </div>
      </div>
    )
  }

  const repo = session?.repository_owner && session?.repository_name
    ? `${session.repository_owner}/${session.repository_name}`
    : null

  const isTerminal = ['completed', 'failed', 'terminated'].includes(session?.status || '')
  const canFollowUp = session?.status === 'completed' || session?.status === 'failed'

  return (
    <div className="session-workspace" style={{
      minHeight: '100vh',
      background: 'var(--bg)',
      display: 'flex',
      flexDirection: 'column',
    }}>
      <SessionHeader
        title={session?.title || 'Session'}
        status={session?.status || 'queued'}
        repo={repo}
        githubRunUrl={session?.github_run_url}
        onBack={() => navigate('/app')}
        onTerminate={handleTerminate}
        onToggleSessions={isMobile ? () => setSessionsOpen(true) : undefined}
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
        <div className="session-pr-banner" style={{
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
              whiteSpace: 'nowrap',
            }}
          >
            View PR
          </a>
        </div>
      )}

      <div className="session-layout" style={{
        flex: 1,
        display: 'grid',
        gridTemplateColumns: isMobile ? '1fr' : 'minmax(280px, 340px) 1fr',
        gap: 0,
        minHeight: 0,
        marginTop: 12,
      }}>
        {/* Left: prompt + thinking stream */}
        {(!isMobile || showTaskPanel) && (
          <aside className="session-aside" style={{
            borderRight: isMobile ? 'none' : '1px solid var(--border-subtle)',
            borderBottom: isMobile ? '1px solid var(--border-subtle)' : 'none',
            display: 'flex',
            flexDirection: 'column',
            background: 'var(--bg-elevated)',
            minHeight: isMobile ? 280 : 0,
            maxHeight: isMobile ? '45vh' : 'none',
          }}>
            {isMobile && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 14px',
                borderBottom: '1px solid var(--border-subtle)',
              }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}>Task & output</span>
                <button
                  type="button"
                  onClick={() => setShowTaskPanel(false)}
                  style={{ background: 'transparent', border: 'none', color: 'var(--text-faint)', cursor: 'pointer', fontSize: 12 }}
                >
                  Hide
                </button>
              </div>
            )}

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
                      <span style={{
                        fontSize: 10,
                        color: entry.phase === 'follow-up' ? 'var(--warning)' : 'var(--accent-hover)',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                      }}>
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

            <FollowUpComposer disabled={!canFollowUp} onSend={sendMessage} />
          </aside>
        )}

        {/* Right: tabbed workspace */}
        <main style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          {isMobile && !showTaskPanel && (
            <button
              type="button"
              onClick={() => setShowTaskPanel(true)}
              style={{
                margin: '8px 12px 0',
                padding: '10px 14px',
                borderRadius: 10,
                border: '1px solid var(--border)',
                background: 'var(--bg-card)',
                color: 'var(--text-muted)',
                fontSize: 12,
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              Show task & agent output
            </button>
          )}

          <nav style={{
            display: 'flex',
            gap: 4,
            padding: '8px 12px',
            borderBottom: '1px solid var(--border-subtle)',
            background: 'var(--bg-elevated)',
            overflowX: 'auto',
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
                  whiteSpace: 'nowrap',
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

          <div style={{ flex: 1, minHeight: isMobile ? 320 : 0, overflow: 'hidden' }}>
            {tab === 'progress' && (
              <ProgressPanel plan={plan} devboxMessage={devboxMessage} events={events} />
            )}
            {tab === 'shell' && <ShellPanel entries={shellEntries} />}
            {tab === 'files' && <FilesPanel files={fileChanges} />}
          </div>
        </main>
      </div>

      {/* Desktop session history rail */}
      {!isMobile && (
        <aside className="session-history-rail" style={{
          position: 'fixed',
          right: 0,
          top: '50%',
          transform: 'translateY(-50%)',
          width: 44,
          zIndex: 40,
        }}>
          <button
            type="button"
            onClick={() => setSessionsOpen(v => !v)}
            title="Session history"
            style={{
              width: 44,
              height: 44,
              borderRadius: '12px 0 0 12px',
              border: '1px solid var(--border)',
              borderRight: 'none',
              background: 'var(--bg-elevated)',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Icon name="clock" size={16} />
          </button>
        </aside>
      )}

      {sessionsOpen && (
        <>
          <div
            onClick={() => setSessionsOpen(false)}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.5)',
              backdropFilter: 'blur(4px)',
              zIndex: 80,
            }}
          />
          <div style={{
            position: 'fixed',
            top: 0,
            right: 0,
            bottom: 0,
            width: isMobile ? 'min(320px, 90vw)' : 320,
            background: 'var(--bg-elevated)',
            borderLeft: '1px solid var(--border-subtle)',
            zIndex: 90,
            display: 'flex',
            flexDirection: 'column',
            animation: 'slideInRight 0.25s ease',
          }}>
            <div style={{
              padding: '16px 18px',
              borderBottom: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>Agent sessions</div>
                <div style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 2 }}>Recent work across repos</div>
              </div>
              <button
                type="button"
                onClick={() => setSessionsOpen(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-faint)', cursor: 'pointer' }}
              >
                <Icon name="close" size={18} />
              </button>
            </div>
            <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>
              <SessionList
                sessions={sessions}
                activeSessionId={sessionId}
                loading={sessionsLoading}
                onSelect={id => {
                  setSessionsOpen(false)
                  navigate(`/app/session/${id}`)
                }}
              />
            </div>
          </div>
        </>
      )}
    </div>
  )
}
