import Icon from '../Icon'

interface PlanStep {
  id: string
  title: string
  goal?: string
  status?: string
}

interface Props {
  plan: Record<string, unknown> | null
  devboxMessage?: string
  events: { type: string; payload: Record<string, unknown>; timestamp: number }[]
}

export default function ProgressPanel({ plan, devboxMessage, events }: Props) {
  const steps = (plan?.steps as PlanStep[]) || []
  const summary = String(plan?.summary || '')

  return (
    <div style={{ padding: 20, height: '100%', overflow: 'auto' }}>
      {summary && (
        <div style={{
          marginBottom: 24,
          padding: 16,
          borderRadius: 12,
          background: 'var(--accent-glow)',
          border: '1px solid rgba(99,102,241,0.2)',
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent-hover)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
            Mission
          </div>
          <div style={{ fontSize: 14, color: 'var(--text)', lineHeight: 1.6 }}>{summary}</div>
        </div>
      )}

      {devboxMessage && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '12px 14px',
          marginBottom: 20,
          borderRadius: 10,
          background: 'var(--bg-card)',
          border: '1px solid var(--border)',
          fontSize: 13,
          color: 'var(--text-muted)',
        }}>
          <Icon name="loading" size={14} />
          {devboxMessage}
        </div>
      )}

      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
        Progress
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {steps.length === 0 ? (
          <div style={{ color: 'var(--text-faint)', fontSize: 13, padding: 20, textAlign: 'center' }}>
            Planning your session…
          </div>
        ) : steps.map((step, i) => {
          const status = step.status || 'pending'
          const isActive = status === 'active'
          const isDone = status === 'completed'
          const isFailed = status === 'failed'

          return (
            <div
              key={step.id || i}
              style={{
                display: 'flex',
                gap: 14,
                padding: '14px 12px',
                borderRadius: 10,
                background: isActive ? 'rgba(99,102,241,0.08)' : 'transparent',
                border: isActive ? '1px solid rgba(99,102,241,0.2)' : '1px solid transparent',
                transition: 'all 0.2s ease',
              }}
            >
              <div style={{
                width: 28,
                height: 28,
                borderRadius: 8,
                flexShrink: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 12,
                fontWeight: 700,
                background: isDone ? 'rgba(52,211,153,0.15)' : isFailed ? 'rgba(239,68,68,0.15)' : isActive ? 'var(--accent-glow)' : 'var(--bg-card)',
                color: isDone ? 'var(--success)' : isFailed ? 'var(--error)' : isActive ? 'var(--accent-hover)' : 'var(--text-faint)',
                border: `1px solid ${isDone ? 'rgba(52,211,153,0.3)' : isFailed ? 'rgba(239,68,68,0.3)' : isActive ? 'rgba(99,102,241,0.3)' : 'var(--border)'}`,
              }}>
                {isDone ? '✓' : isFailed ? '✕' : isActive ? <Icon name="loading" size={12} /> : i + 1}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 500, color: isActive ? 'var(--text)' : isDone ? 'var(--text-muted)' : 'var(--text-dim)' }}>
                  {step.title}
                </div>
                {step.goal && (
                  <div style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 4, lineHeight: 1.5 }}>
                    {step.goal}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {events.length > 0 && (
        <>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', margin: '28px 0 12px' }}>
            Activity
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {events.filter(e => ['thinking', 'step_started', 'step_completed', 'devbox_status'].includes(e.type)).slice(-12).map((e, i) => (
              <div key={i} style={{ fontSize: 12, color: 'var(--text-dim)', padding: '6px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                <span style={{ color: 'var(--text-faint)', marginRight: 8 }}>
                  {new Date(e.timestamp).toLocaleTimeString()}
                </span>
                {String(e.payload.message || e.payload.content || e.payload.summary || e.type).slice(0, 120)}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
