import { useState, useEffect, useRef } from 'react'
import Icon from './Icon'

export interface TimelineStep {
  step: string
  status: 'pending' | 'running' | 'done' | 'error' | 'skip' | 'warn'
  message: string
}

export interface AgentRun {
  taskId: string
  repo: string
  branch: string
  task: string
  status: 'running' | 'done' | 'error'
  timeline: TimelineStep[]
  plan: string[]
  modifiedFiles: string[]
  thinking: { iteration: number; thought: string }[]
  toolCalls: { tool: string; params: Record<string, string>; iteration: number }[]
  observations: { iteration: number; tool: string; output: string }[]
  prUrl: string
  prNumber: string | number
  commitHash: string
  durationSeconds: number
  error: string
}

interface Props {
  run: AgentRun | null
  isOpen: boolean
  onClose: () => void
}

const STEP_LABELS: Record<string, string> = {
  init: 'Connect',
  workspace: 'Workspace',
  branch: 'Branch',
  analysis: 'Analyze',
  planning: 'Plan',
  execution: 'Execute',
  commit: 'Commit',
  push: 'Push',
  pr: 'Pull Request',
}

const STATUS_COLOR: Record<string, string> = {
  pending: 'var(--text-faint)',
  running: 'var(--accent-hover)',
  done: 'var(--success)',
  error: 'var(--error)',
  skip: 'var(--text-faint)',
  warn: 'var(--warning)',
}

const STATUS_ICON: Record<string, string> = {
  pending: '○',
  running: '◐',
  done: '✓',
  error: '✗',
  skip: '—',
  warn: '⚠',
}

type Tab = 'overview' | 'plan' | 'output'

export default function AgentTimeline({ run, isOpen, onClose }: Props) {
  const [tab, setTab] = useState<Tab>('overview')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (run?.status === 'running') {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [run?.timeline.length])

  if (!isOpen || !run) return null

  const isRunning = run.status === 'running'
  const currentStep = run.timeline.find(s => s.status === 'running')

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Execution details"
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(8px)', zIndex: 400, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, animation: 'fadeIn 0.15s ease' }}
      onClick={onClose}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{ width: '100%', maxWidth: 640, maxHeight: '92vh', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius-xl)', display: 'flex', flexDirection: 'column', overflow: 'hidden', animation: 'modalContent 0.2s ease', boxShadow: '0 32px 80px rgba(0,0,0,0.6)' }}
      >
        {/* Header */}
        <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: isRunning ? 'var(--accent)' : run.status === 'error' ? 'rgba(239,68,68,0.2)' : 'rgba(52,211,153,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              {isRunning
                ? <Icon name="loader" size={16} style={{ color: 'white' }} />
                : run.status === 'error'
                  ? <Icon name="error" size={16} style={{ color: 'var(--error)' }} />
                  : <Icon name="check" size={16} style={{ color: 'var(--success)' }} />
              }
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)', maxWidth: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{run.task}</div>
              <div style={{ fontSize: 11, color: 'var(--text-faint)', display: 'flex', alignItems: 'center', gap: 8, marginTop: 2 }}>
                <span>{run.repo}</span>
                {run.branch && <><span>·</span><span style={{ fontFamily: 'monospace', color: 'var(--text-dim)' }}>{run.branch.replace('devbuddy/', '')}</span></>}
                {run.durationSeconds > 0 && <><span>·</span><span>{run.durationSeconds}s</span></>}
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {run.prUrl && (
              <a href={run.prUrl} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: 'var(--accent-light)', textDecoration: 'none', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
                <Icon name="git-pull" size={12} /> PR #{run.prNumber}
              </a>
            )}
            <button onClick={onClose} className="db-btn db-focus" aria-label="Close" style={{ background: 'none', border: 'none', color: 'var(--text-faint)', cursor: 'pointer', padding: 4, borderRadius: 'var(--radius-sm)', display: 'flex' }}>
              <Icon name="close" size={16} />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border-subtle)', flexShrink: 0 }}>
          {([
            { id: 'overview' as Tab, label: 'Overview' },
            { id: 'plan' as Tab, label: 'Plan' },
            { id: 'output' as Tab, label: 'Output' },
          ]).map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className="db-btn"
              style={{ padding: '10px 16px', fontSize: 13, fontWeight: tab === t.id ? 600 : 400, color: tab === t.id ? 'var(--text)' : 'var(--text-faint)', background: 'none', border: 'none', borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent', cursor: 'pointer', transition: 'all 0.15s' }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '20px' }}>

          {/* Overview */}
          {tab === 'overview' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Status line */}
              <div style={{ fontSize: 14, color: isRunning ? 'var(--accent-light)' : run.status === 'error' ? 'var(--error)' : 'var(--success)' }}>
                {isRunning ? (currentStep?.message || 'Working...') : run.status === 'error' ? run.error || 'Execution failed' : 'Task completed successfully'}
              </div>

              {/* Step list */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {Object.entries(STEP_LABELS).map(([key, label]) => {
                  const step = run.timeline.find(s => s.step === key)
                  const status = step?.status ?? 'pending'
                  return (
                    <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0' }}>
                      <div style={{
                        width: 8, height: 8, borderRadius: '50%',
                        background: status === 'done' ? '#22c55e' : status === 'running' ? '#6366f1' : status === 'error' ? '#ef4444' : 'var(--border)',
                        boxShadow: status === 'running' ? '0 0 8px rgba(99,102,241,0.5)' : 'none',
                        animation: status === 'running' ? 'pulse 2s ease-in-out infinite' : 'none',
                      }} />
                      <span style={{ fontSize: 13, color: status === 'pending' ? 'var(--text-faint)' : 'var(--text)' }}>{label}</span>
                      {step?.message && (
                        <span style={{ fontSize: 12, color: 'var(--text-dim)', marginLeft: 'auto' }}>{step.message}</span>
                      )}
                    </div>
                  )
                })}
              </div>

              {run.error && (
                <div style={{ padding: '12px 16px', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--radius-md)', fontSize: 13, color: 'var(--error)' }}>
                  {run.error}
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}

          {/* Plan */}
          {tab === 'plan' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {run.plan.length === 0
                ? <Empty text="Plan not yet generated" />
                : run.plan.map((step, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '8px 12px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}>
                    <span style={{ fontSize: 11, color: 'var(--accent-light)', background: 'rgba(99,102,241,0.1)', padding: '2px 7px', borderRadius: 8, fontWeight: 700, flexShrink: 0, marginTop: 1 }}>{i + 1}</span>
                    <span style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.5 }}>{step}</span>
                  </div>
                ))
              }
            </div>
          )}

          {/* Output */}
          {tab === 'output' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {run.modifiedFiles.length === 0
                ? <Empty text="No files modified yet" />
                : (
                  <>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>Files changed</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {run.modifiedFiles.map(f => (
                        <div key={f} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', background: 'var(--bg-card)', borderRadius: 'var(--radius-sm)' }}>
                          <Icon name="file" size={12} style={{ color: 'var(--success)', flexShrink: 0 }} />
                          <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--text-muted)' }}>{f}</span>
                        </div>
                      ))}
                    </div>
                  </>
                )
              }
              {run.commitHash && (
                <div style={{ fontSize: 12, color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: 6, marginTop: 8 }}>
                  <Icon name="check" size={12} style={{ color: 'var(--success)' }} />
                  Commit <code style={{ fontFamily: 'monospace', background: 'var(--bg-card)', padding: '2px 6px', borderRadius: 4 }}>{run.commitHash}</code>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return <div style={{ padding: '32px 0', textAlign: 'center', color: 'var(--text-faint)', fontSize: 13 }}>{text}</div>
}
