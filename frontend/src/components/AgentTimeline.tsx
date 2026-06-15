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

type Tab = 'timeline' | 'plan' | 'files' | 'thinking' | 'tools'

export default function AgentTimeline({ run, isOpen, onClose }: Props) {
  const [tab, setTab] = useState<Tab>('timeline')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (run?.status === 'running') {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [run?.timeline.length, run?.thinking.length])

  if (!isOpen || !run) return null

  const isRunning = run.status === 'running'

  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(8px)', zIndex: 400, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, animation: 'fadeIn 0.15s ease' }}
      onClick={onClose}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{ width: '100%', maxWidth: 800, maxHeight: '92vh', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius-xl)', display: 'flex', flexDirection: 'column', overflow: 'hidden', animation: 'modalContent 0.2s ease', boxShadow: '0 32px 80px rgba(0,0,0,0.6)' }}
      >
        {/* Header */}
        <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: isRunning ? 'linear-gradient(135deg, var(--accent), var(--accent-hover))' : run.status === 'error' ? 'rgba(239,68,68,0.2)' : 'rgba(52,211,153,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              {isRunning
                ? <Icon name="loader" size={16} style={{ color: 'white' }} />
                : run.status === 'error'
                  ? <Icon name="error" size={16} style={{ color: 'var(--error)' }} />
                  : <Icon name="check" size={16} style={{ color: 'var(--success)' }} />
              }
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', maxWidth: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{run.task}</div>
              <div style={{ fontSize: 11, color: 'var(--text-faint)', display: 'flex', alignItems: 'center', gap: 8, marginTop: 2 }}>
                <Icon name="git" size={10} />
                <span>{run.repo}</span>
                {run.branch && <><span>·</span><span style={{ fontFamily: 'monospace', color: 'var(--accent-hover)' }}>{run.branch.replace('devbuddy/', '')}</span></>}
                {run.durationSeconds > 0 && <><span>·</span><span>{run.durationSeconds}s</span></>}
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {run.prUrl && (
              <a href={run.prUrl} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: 'white', background: 'linear-gradient(135deg, var(--accent), var(--accent-hover))', border: 'none', borderRadius: 'var(--radius-md)', padding: '5px 14px', textDecoration: 'none', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 5 }}>
                <Icon name="git" size={12} /> View PR #{run.prNumber}
              </a>
            )}
            <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-faint)', cursor: 'pointer', padding: 4, borderRadius: 'var(--radius-sm)', display: 'flex' }}>
              <Icon name="close" size={16} />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border-subtle)', flexShrink: 0, overflowX: 'auto' }}>
          {([
            { id: 'timeline', label: 'Timeline', count: run.timeline.length },
            { id: 'plan', label: 'Plan', count: run.plan.length },
            { id: 'files', label: 'Files', count: run.modifiedFiles.length },
            { id: 'thinking', label: 'Reasoning', count: run.thinking.length },
            { id: 'tools', label: 'Tools', count: run.toolCalls.length },
          ] as { id: Tab; label: string; count: number }[]).map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{ padding: '10px 16px', fontSize: 12, fontWeight: tab === t.id ? 600 : 400, color: tab === t.id ? 'var(--text)' : 'var(--text-faint)', background: 'none', border: 'none', borderBottom: tab === t.id ? '2px solid var(--accent-hover)' : '2px solid transparent', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5, whiteSpace: 'nowrap', transition: 'all 0.15s' }}
            >
              {t.label}
              {t.count > 0 && <span style={{ fontSize: 10, background: tab === t.id ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.06)', color: tab === t.id ? 'var(--accent-hover)' : 'var(--text-faint)', padding: '1px 5px', borderRadius: 8, fontWeight: 600 }}>{t.count}</span>}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '16px 20px' }}>

          {/* Timeline */}
          {tab === 'timeline' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {Object.entries(STEP_LABELS).map(([key, label]) => {
                const step = run.timeline.find(s => s.step === key)
                const status = step?.status ?? 'pending'
                const message = step?.message ?? ''
                return (
                  <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px', borderRadius: 'var(--radius-md)', background: status === 'running' ? 'rgba(99,102,241,0.06)' : 'transparent', border: status === 'running' ? '1px solid rgba(99,102,241,0.15)' : '1px solid transparent', transition: 'all 0.2s' }}>
                    <span style={{ fontSize: 13, color: STATUS_COLOR[status], width: 16, textAlign: 'center', flexShrink: 0, animation: status === 'running' ? 'pulse 1.5s infinite' : 'none' }}>
                      {STATUS_ICON[status]}
                    </span>
                    <span style={{ fontSize: 13, fontWeight: 600, color: status === 'pending' ? 'var(--text-faint)' : 'var(--text)', width: 90, flexShrink: 0 }}>{label}</span>
                    <span style={{ fontSize: 12, color: status === 'pending' ? 'var(--text-faint)' : 'var(--text-dim)', flex: 1 }}>{message || (status === 'pending' ? 'Waiting...' : '')}</span>
                    {status === 'running' && <Icon name="loader" size={12} style={{ color: 'var(--accent-hover)', flexShrink: 0 }} />}
                  </div>
                )
              })}
              {run.error && (
                <div style={{ marginTop: 8, padding: '10px 14px', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--radius-md)', fontSize: 12, color: 'var(--error)' }}>
                  {run.error}
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}

          {/* Plan */}
          {tab === 'plan' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {run.plan.length === 0
                ? <Empty text="Plan not yet generated" />
                : run.plan.map((step, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '8px 12px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}>
                    <span style={{ fontSize: 11, color: 'var(--accent-hover)', background: 'rgba(99,102,241,0.1)', padding: '2px 7px', borderRadius: 8, fontWeight: 700, flexShrink: 0, marginTop: 1 }}>{i + 1}</span>
                    <span style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.5 }}>{step}</span>
                  </div>
                ))
              }
            </div>
          )}

          {/* Modified Files */}
          {tab === 'files' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {run.modifiedFiles.length === 0
                ? <Empty text="No files modified yet" />
                : run.modifiedFiles.map(f => (
                  <div key={f} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 12px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}>
                    <Icon name="file" size={12} style={{ color: 'var(--success)', flexShrink: 0 }} />
                    <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--text-muted)' }}>{f}</span>
                  </div>
                ))
              }
              {run.commitHash && (
                <div style={{ marginTop: 8, padding: '8px 12px', background: 'rgba(52,211,153,0.06)', border: '1px solid rgba(52,211,153,0.15)', borderRadius: 'var(--radius-md)', fontSize: 12, color: 'var(--success)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Icon name="check" size={12} /> Commit <code style={{ fontFamily: 'monospace', background: 'rgba(52,211,153,0.1)', padding: '1px 6px', borderRadius: 4 }}>{run.commitHash}</code>
                </div>
              )}
            </div>
          )}

          {/* Reasoning */}
          {tab === 'thinking' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {run.thinking.length === 0
                ? <Empty text="No reasoning yet" />
                : run.thinking.map((t, i) => (
                  <div key={i} style={{ padding: '10px 14px', background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', borderLeft: '3px solid var(--accent)' }}>
                    <div style={{ fontSize: 10, color: 'var(--text-faint)', marginBottom: 4, fontWeight: 600 }}>STEP {t.iteration}</div>
                    <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6 }}>{t.thought}</div>
                  </div>
                ))
              }
            </div>
          )}

          {/* Tool calls */}
          {tab === 'tools' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {run.toolCalls.length === 0
                ? <Empty text="No tool calls yet" />
                : run.toolCalls.map((tc, i) => {
                  const obs = run.observations.find(o => o.iteration === tc.iteration)
                  return (
                    <div key={i} style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
                      <div style={{ padding: '7px 12px', display: 'flex', alignItems: 'center', gap: 8, borderBottom: obs ? '1px solid var(--border-subtle)' : 'none' }}>
                        <span style={{ fontSize: 10, color: 'var(--accent-hover)', background: 'rgba(99,102,241,0.1)', padding: '1px 6px', borderRadius: 6, fontWeight: 700, fontFamily: 'monospace' }}>{tc.tool}</span>
                        {Object.entries(tc.params).slice(0, 2).map(([k, v]) => (
                          <span key={k} style={{ fontSize: 11, color: 'var(--text-faint)' }}><span style={{ color: 'var(--text-dim)' }}>{k}:</span> {String(v).substring(0, 50)}{String(v).length > 50 ? '…' : ''}</span>
                        ))}
                      </div>
                      {obs && (
                        <div style={{ padding: '6px 12px', fontSize: 11, color: 'var(--text-faint)', fontFamily: 'monospace', whiteSpace: 'pre-wrap', maxHeight: 80, overflow: 'hidden' }}>
                          {obs.output.substring(0, 300)}
                        </div>
                      )}
                    </div>
                  )
                })
              }
            </div>
          )}
        </div>

        {/* Footer */}
        {(run.commitHash || run.modifiedFiles.length > 0) && (
          <div style={{ padding: '10px 20px', borderTop: '1px solid var(--border-subtle)', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-faint)' }}>
            <span>{run.modifiedFiles.length} file{run.modifiedFiles.length !== 1 ? 's' : ''} changed · {run.toolCalls.length} tool calls</span>
            {run.prUrl && (
              <a href={run.prUrl} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-hover)', textDecoration: 'none', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
                <Icon name="git" size={12} /> Open PR ↗
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return <div style={{ padding: '32px 0', textAlign: 'center', color: 'var(--text-faint)', fontSize: 13 }}>{text}</div>
}
