/**
 * TaskCard — Engineering progress, not CI logs.
 *
 * Each user message becomes a TaskCard. Events are grouped into
 * human-readable phases so the user feels like they're supervising
 * a senior engineer, not debugging a pipeline.
 *
 * Design principles:
 *  - Group raw events into 4 meaningful phases
 *  - Show only what's happening now + what's done
 *  - One color for active (accent), one for done (muted), one for error (red)
 *  - No durations, no expand chevrons, no technical jargon
 */

import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import Icon, { IconName } from './Icon'

// ── Types ────────────────────────────────────────────────────────────────────

export type EventCategory =
  | 'plan'
  | 'context'
  | 'search'
  | 'read'
  | 'analyze'
  | 'execute'
  | 'test'
  | 'reflect'
  | 'branch'
  | 'commit'
  | 'push'
  | 'pr'
  | 'tool'
  | 'think'
  | 'observe'
  | 'warn'
  | 'error'
  | 'done'
  | 'step'

export interface TaskEvent {
  id: string
  category: EventCategory
  title: string
  detail?: string
  status: 'running' | 'done' | 'error' | 'warn' | 'skip'
  ts: number
  durationMs?: number
  expandable?: boolean
  children?: string[]
  meta?: Record<string, any>
}

export type RunnerState =
  | 'queued' | 'provisioning' | 'initializing' | 'connecting'
  | 'analyzing' | 'executing' | 'validating' | 'reflecting'
  | 'pushing' | 'creating_pr' | 'uploading' | 'completed' | 'destroyed'

export interface QualityGate {
  name: string
  status: 'pass' | 'fail' | 'warn' | 'skip' | 'pending'
}

export interface TaskCardData {
  id: string
  task: string
  repo?: string
  branch?: string
  startedAt: number
  status: 'running' | 'done' | 'error'
  progress: number
  currentTool?: string
  events: TaskEvent[]
  answer?: string
  prUrl?: string
  prNumber?: string | number
  commitHash?: string
  modifiedFiles?: string[]
  isGitHubTask?: boolean
  isCloudJob?: boolean
  runnerState?: RunnerState
  runUrl?: string
  runId?: number
  qualityGates?: Record<string, string>
}

interface TaskCardProps {
  card: TaskCardData
  userAvatar?: string | null
  userName?: string
  isStreaming?: boolean
  onRetry?: () => void
}

// ── Phase grouping: raw events → human-readable phases ──────────────────────

type PhaseType = 'plan' | 'read' | 'execute' | 'deliver'

interface PhaseGroup {
  type: PhaseType
  label: string
  icon: IconName
  events: TaskEvent[]
  status: 'pending' | 'active' | 'done' | 'error'
}

const PHASE_ORDER: PhaseType[] = ['plan', 'read', 'execute', 'deliver']

const PHASE_META: Record<PhaseType, { label: string; icon: IconName }> = {
  plan:    { label: 'Planning',      icon: 'brain'     },
  read:    { label: 'Understanding', icon: 'book'     },
  execute: { label: 'Implementing',  icon: 'code'     },
  deliver: { label: 'Delivering',    icon: 'git-pull' },
}

/** Map event categories to their phase */
function eventPhase(category: EventCategory): PhaseType {
  switch (category) {
    case 'plan':
    case 'think':
    case 'analyze':
      return 'plan'
    case 'context':
    case 'search':
    case 'read':
    case 'observe':
      return 'read'
    case 'execute':
    case 'tool':
    case 'test':
    case 'reflect':
      return 'execute'
    case 'branch':
    case 'commit':
    case 'push':
    case 'pr':
    case 'done':
      return 'deliver'
    case 'warn':
    case 'error':
    case 'step':
    default:
      return 'execute'
  }
}

/** Group flat events into phases */
function groupEvents(events: TaskEvent[]): PhaseGroup[] {
  const groups = new Map<PhaseType, TaskEvent[]>()
  for (const evt of events) {
    const phase = eventPhase(evt.category)
    if (!groups.has(phase)) groups.set(phase, [])
    groups.get(phase)!.push(evt)
  }

  return PHASE_ORDER.map(type => {
    const evts = groups.get(type) ?? []
    const hasError = evts.some(e => e.status === 'error')
    const hasRunning = evts.some(e => e.status === 'running')
    const hasDone = evts.some(e => e.status === 'done')
    const status: PhaseGroup['status'] = hasError ? 'error' : hasRunning ? 'active' : hasDone ? 'done' : 'pending'
    return { type, ...PHASE_META[type], events: evts, status }
  }).filter(g => g.events.length > 0)
}

function liveElapsed(startedAt: number): string {
  const ms = Date.now() - startedAt
  if (ms < 60000) return `${Math.floor(ms / 1000)}s`
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`
}

// ── Phase row: one row per phase, not per event ─────────────────────────────

function PhaseRow({ group, isLast }: { group: PhaseGroup; isLast: boolean }) {
  const { label, status, events } = group
  const isActive = status === 'active'
  const isDone = status === 'done'
  const isError = status === 'error'
  const [expanded, setExpanded] = useState(false)
  const canExpand = events.length > 1 && (isDone || isError)

  // Build a human summary from the events
  const latestEvent = events[events.length - 1]
  const summary = isActive && latestEvent
    ? latestEvent.title
    : isDone
      ? `${events.length} steps completed`
      : isError
        ? 'Issue encountered'
        : 'Waiting...'

  return (
    <div>
      <div
        onClick={() => canExpand && setExpanded(x => !x)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '6px 0',
          opacity: status === 'pending' ? 0.5 : 1,
          transition: 'opacity 0.3s ease',
          cursor: canExpand ? 'pointer' : 'default',
        }}
      >
        {/* Status dot */}
        <div style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          flexShrink: 0,
          background: isError ? '#ef4444' : isActive ? '#6366f1' : isDone ? '#22c55e' : 'var(--border)',
          boxShadow: isActive ? '0 0 8px rgba(99,102,241,0.5)' : 'none',
          animation: isActive ? 'pulse 2s ease-in-out infinite' : 'none',
        }} />

        {/* Phase label + summary */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 12.5,
            fontWeight: isActive ? 500 : 400,
            color: isError ? '#ef4444' : isActive ? 'var(--text)' : isDone ? 'var(--text-muted)' : 'var(--text-faint)',
            lineHeight: 1.4,
          }}>
            {label}
            <span style={{
              color: isActive ? 'var(--text-dim)' : 'var(--text-faint)',
              fontWeight: 400,
              marginLeft: 6,
            }}>
              — {summary}
            </span>
          </div>
        </div>

        {/* Expand chevron (done phases with multiple events) */}
        {canExpand && (
          <Icon
            name="chevron-down"
            size={11}
            style={{
              color: 'var(--text-faint)',
              flexShrink: 0,
              transition: 'transform 0.15s ease',
              transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            }}
          />
        )}

        {/* Running spinner */}
        {isActive && (
          <Icon name="loader" size={11} style={{ color: '#6366f1', flexShrink: 0 }} />
        )}

        {/* Done check */}
        {isDone && !canExpand && (
          <Icon name="check" size={11} style={{ color: '#22c55e', flexShrink: 0, opacity: 0.7 }} />
        )}
      </div>

      {/* Expanded event list */}
      {expanded && canExpand && (
        <div style={{
          marginLeft: 18,
          paddingLeft: 12,
          borderLeft: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          animation: 'fadeIn 0.15s ease',
        }}>
          {events.map((evt, i) => (
            <div key={i} style={{
              fontSize: 12,
              color: evt.status === 'error' ? '#ef4444' : 'var(--text-dim)',
              lineHeight: 1.4,
              padding: '2px 0',
            }}>
              {evt.title}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ProgressBar({ progress, status }: { progress: number; status: string }) {
  return (
    <div style={{ height: 2, background: 'rgba(255,255,255,0.06)', borderRadius: 1, overflow: 'hidden' }}>
      <div style={{
        height: '100%',
        width: `${Math.max(2, progress)}%`,
        background: status === 'error' ? '#ef4444' : status === 'done' ? '#22c55e' : '#6366f1',
        transition: 'width 0.4s ease',
        borderRadius: 1,
      }} />
    </div>
  )
}

// ── Main Component ─────────────────────────────────────────────────────────

export default function TaskCard({ card, userAvatar, userName, isStreaming, onRetry }: TaskCardProps) {
  const [elapsed2, setElapsed2] = useState(() => liveElapsed(card.startedAt))
  const [showAnswer, setShowAnswer] = useState(false)
  const eventsEndRef = useRef<HTMLDivElement>(null)

  // Live clock while running
  useEffect(() => {
    if (card.status !== 'running') return
    const t = setInterval(() => setElapsed2(liveElapsed(card.startedAt)), 1000)
    return () => clearInterval(t)
  }, [card.status, card.startedAt])

  // Auto-scroll to bottom of events
  useEffect(() => {
    if (card.status === 'running') {
      eventsEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }, [card.events.length])

  // Auto-show answer when done
  useEffect(() => {
    if (card.status === 'done' && card.answer) {
      const t = setTimeout(() => setShowAnswer(true), 300)
      return () => clearTimeout(t)
    }
  }, [card.status, card.answer])

  const isRunning = card.status === 'running'

  return (
    <div style={{ marginBottom: 32, animation: 'messageIn 0.25s ease' }}>

      {/* ── User instruction ─── */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 12, justifyContent: 'flex-end' }}>
        <div style={{
          maxWidth: '72%',
          background: 'rgba(99,102,241,0.1)',
          border: '1px solid rgba(99,102,241,0.2)',
          borderRadius: '16px 16px 4px 16px',
          padding: '12px 16px',
        }}>
          <div style={{ fontSize: 14, color: '#e2e8f0', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>{card.task}</div>
          {(card.repo || card.branch) && (
            <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              {card.repo && (
                <span style={{ fontSize: 11, color: '#818cf8', background: 'rgba(99,102,241,0.12)', padding: '2px 8px', borderRadius: 10, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Icon name="git" size={10} style={{ color: '#818cf8' }} /> {card.repo}
                </span>
              )}
              {card.branch && (
                <span style={{ fontSize: 11, color: '#4ade80', background: 'rgba(52,211,153,0.1)', padding: '2px 8px', borderRadius: 10, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Icon name="branch" size={10} style={{ color: '#4ade80' }} />
                  <span style={{ fontFamily: 'monospace' }}>{card.branch.replace('devbuddy/', '')}</span>
                </span>
              )}
            </div>
          )}
        </div>
        <div style={{ width: 32, height: 32, borderRadius: '50%', flexShrink: 0, overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(99,102,241,0.2)', border: '2px solid rgba(99,102,241,0.15)' }}>
          {userAvatar
            ? <img src={userAvatar} alt={userName || 'User'} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            : <Icon name="user" size={15} style={{ color: '#818cf8' }} />
          }
        </div>
      </div>

      {/* ── Agent work card ─── */}
      {(card.events.length > 0 || isRunning) && (
        <div style={{ display: 'flex', gap: 12 }}>
          {/* Agent avatar */}
          <div style={{
            width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: isRunning ? 'linear-gradient(135deg, #6366f1, #818cf8)' : card.status === 'error' ? 'rgba(239,68,68,0.2)' : 'rgba(52,211,153,0.15)',
            border: `2px solid ${isRunning ? 'rgba(99,102,241,0.4)' : card.status === 'error' ? 'rgba(239,68,68,0.3)' : 'rgba(52,211,153,0.2)'}`,
            boxShadow: isRunning ? '0 0 12px rgba(99,102,241,0.3)' : 'none',
            transition: 'all 0.3s',
          }}>
            <Icon name={isRunning ? 'loader' : card.status === 'error' ? 'error' : 'check'} size={14} style={{ color: isRunning ? 'white' : card.status === 'error' ? '#ef4444' : '#34d399' }} />
          </div>

          {/* Card body */}
          <div style={{
            flex: 1,
            minWidth: 0,
            background: 'var(--bg-card)',
            border: `1px solid ${isRunning ? 'rgba(99,102,241,0.2)' : card.status === 'error' ? 'rgba(239,68,68,0.2)' : 'rgba(52,211,153,0.12)'}`,
            borderRadius: '4px 16px 16px 16px',
            overflow: 'hidden',
            transition: 'border-color 0.3s',
            boxShadow: isRunning ? '0 4px 20px rgba(99,102,241,0.08)' : '0 2px 12px rgba(0,0,0,0.12)',
          }}>

            {/* Card header */}
            <div style={{ padding: '12px 14px', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: isRunning ? 'var(--accent-light)' : card.status === 'error' ? 'var(--error)' : 'var(--success)', flexShrink: 0 }}>
                  {isRunning ? 'Working' : card.status === 'error' ? 'Failed' : 'Complete'}
                </span>
                <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>
                  {isRunning ? elapsed2 : card.modifiedFiles && card.modifiedFiles.length > 0 ? `${card.modifiedFiles.length} file${card.modifiedFiles.length !== 1 ? 's' : ''}` : ''}
                </span>
              </div>

              {/* Progress bar */}
              {(isRunning || card.status === 'done' || card.status === 'error') && (
                <div style={{ marginTop: 10 }}>
                  <ProgressBar progress={card.progress} status={card.status} />
                </div>
              )}
            </div>

            {/* Phase timeline */}
            <div style={{ padding: '8px 14px', maxHeight: isRunning ? 280 : 220, overflowY: 'auto' }}>
              {(() => {
                const phases = groupEvents(card.events)
                if (phases.length === 0 && isRunning) {
                  return (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#6366f1', animation: 'pulse 2s ease-in-out infinite' }} />
                      <span style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>Starting up...</span>
                    </div>
                  )
                }
                return phases.map((g, i) => (
                  <PhaseRow key={g.type} group={g} isLast={i === phases.length - 1} />
                ))
              })()}
              <div ref={eventsEndRef} />
            </div>

            {/* Result bar */}
            {card.status === 'done' && (card.prUrl || card.commitHash || (card.modifiedFiles && card.modifiedFiles.length > 0)) && (
              <div style={{ padding: '10px 14px', borderTop: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                {card.modifiedFiles && card.modifiedFiles.length > 0 && (
                  <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Icon name="file" size={12} /> {card.modifiedFiles.length} file{card.modifiedFiles.length !== 1 ? 's' : ''}
                  </span>
                )}
                {card.prUrl && (
                  <a href={card.prUrl} target="_blank" rel="noopener noreferrer"
                    style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-light)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Icon name="git-pull" size={12} /> Review PR {card.prNumber ? `#${card.prNumber}` : ''}
                  </a>
                )}
                {card.commitHash && (
                  <span style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'monospace' }}>
                    {card.commitHash.slice(0, 7)}
                  </span>
                )}
              </div>
            )}

            {/* Error */}
            {card.status === 'error' && onRetry && (
              <div style={{ padding: '10px 14px', borderTop: '1px solid rgba(239,68,68,0.15)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <button onClick={onRetry} className="db-btn db-focus" style={{ fontSize: 12, color: 'var(--error)', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--radius-md)', padding: '5px 12px', cursor: 'pointer' }}>
                  <Icon name="refresh" size={11} /> Retry
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Answer block (non-GitHub chat response) ─── */}
      {card.answer && (
        <div style={{ display: 'flex', gap: 12, marginTop: 12, animation: showAnswer ? 'messageIn 0.25s ease' : 'none', opacity: showAnswer ? 1 : 0, transition: 'opacity 0.3s' }}>
          <div style={{ width: 32, height: 32, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(52,211,153,0.15)', border: '2px solid rgba(52,211,153,0.2)' }}>
            <Icon name="bot" size={15} style={{ color: '#34d399' }} />
          </div>
          <div style={{ flex: 1, minWidth: 0, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '4px 16px 16px 16px', padding: '14px 18px' }}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code: ({ node, className, children, ...props }: any) => {
                  const inline = !className
                  if (inline) return (
                    <code style={{ background: 'rgba(99,102,241,0.12)', padding: '1px 5px', borderRadius: 4, fontSize: '0.88em', fontFamily: 'monospace', color: '#c4b5fd' }}>{children}</code>
                  )
                  return (
                    <div style={{ background: '#0d1117', border: '1px solid #21262d', borderRadius: 8, margin: '10px 0', overflow: 'auto' }}>
                      <div style={{ padding: '6px 12px', borderBottom: '1px solid #21262d', fontSize: 11, color: '#6e7681', fontFamily: 'monospace' }}>
                        {className?.replace('language-', '') || 'code'}
                      </div>
                      <pre style={{ margin: 0, padding: '12px', fontSize: 13, fontFamily: 'monospace', overflowX: 'auto', color: '#e6edf3', lineHeight: 1.6 }}>
                        <code>{children}</code>
                      </pre>
                    </div>
                  )
                },
                pre: ({ children }: any) => <>{children}</>,
                p: ({ children }: any) => <p style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--text)', marginBottom: 8, marginTop: 0 }}>{children}</p>,
                ul: ({ children }: any) => <ul style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--text)', paddingLeft: 20, marginBottom: 8 }}>{children}</ul>,
                ol: ({ children }: any) => <ol style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--text)', paddingLeft: 20, marginBottom: 8 }}>{children}</ol>,
                li: ({ children }: any) => <li style={{ marginBottom: 4 }}>{children}</li>,
                strong: ({ children }: any) => <strong style={{ color: 'var(--accent-hover)', fontWeight: 600 }}>{children}</strong>,
                a: ({ children, href }: any) => <a href={href} style={{ color: 'var(--accent-hover)', textDecoration: 'underline' }} target="_blank" rel="noopener noreferrer">{children}</a>,
                h1: ({ children }: any) => <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)', margin: '12px 0 6px' }}>{children}</h1>,
                h2: ({ children }: any) => <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)', margin: '10px 0 4px' }}>{children}</h2>,
                h3: ({ children }: any) => <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)', margin: '8px 0 4px' }}>{children}</h3>,
              }}
            >
              {card.answer}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Utility: convert raw SSE event types to TaskEvent ─────────────────────────

export function sseToTaskEvent(type: string, payload: any): TaskEvent | null {
  const id = Math.random().toString(36).slice(2, 9)
  const ts = Date.now()

  switch (type) {
    case 'timeline':
      return {
        id, ts, category: payload.step as EventCategory ?? 'step',
        title: payload.message || payload.step,
        status: payload.status === 'done' ? 'done' : payload.status === 'error' ? 'error' : payload.status === 'warn' ? 'warn' : 'running',
        durationMs: undefined,
      }
    case 'thinking':
      return {
        id, ts, category: 'think',
        title: payload.thought?.slice(0, 100) ?? 'Reasoning…',
        status: 'done',
        expandable: payload.thought?.length > 100,
        children: payload.thought ? [payload.thought] : undefined,
      }
    case 'plan':
      return {
        id, ts, category: 'plan',
        title: `Execution plan · ${payload.steps?.length ?? 0} steps`,
        status: 'done',
        expandable: true,
        children: payload.steps ?? [],
      }
    case 'tool_call':
      return {
        id, ts, category: 'tool',
        title: `${toolLabel(payload.tool)} ${firstParam(payload.params)}`,
        status: 'running',
        expandable: false,
      }
    case 'observation': {
      const prev = null // handled by caller patching previous event
      return {
        id, ts, category: 'observe',
        title: `${toolLabel(payload.tool)} → ${payload.output?.slice(0, 60) ?? ''}`,
        status: 'done',
        expandable: (payload.output?.length ?? 0) > 60,
        children: payload.output ? [payload.output] : undefined,
      }
    }
    case 'file_change':
      return {
        id, ts, category: 'execute',
        title: `${payload.action === 'create_file' ? 'Created' : payload.action === 'edit_file' ? 'Edited' : 'Modified'} ${payload.path}`,
        status: 'done',
      }
    case 'analysis':
      return {
        id, ts, category: 'analyze',
        title: `Analyzed ${payload.file_count ?? '?'} files`,
        status: 'done',
        expandable: !!payload.tree_preview,
        children: payload.tree_preview ? payload.tree_preview.split('\n').slice(0, 20) : undefined,
      }
    case 'branch':
      return {
        id, ts, category: 'branch',
        title: `Branch ready: ${payload.name?.replace('devbuddy/', '') ?? ''}`,
        status: 'done',
      }
    case 'pr':
      return {
        id, ts, category: 'pr',
        title: `Pull Request #${payload.number} opened`,
        status: 'done',
        expandable: !!payload.url,
        children: payload.url ? [payload.url] : undefined,
      }
    case 'runner':
      return {
        id, ts, category: 'step',
        title: payload.message ?? payload.state ?? 'Runner',
        status: payload.state === 'completed' || payload.state === 'destroyed' ? 'done'
          : payload.state === 'queued' ? 'skip' : 'running',
        detail: payload.run_url,
      }
    case 'quality_gates':
      return null // handled separately on the card data
    case 'log':
      return {
        id, ts, category: 'observe',
        title: payload.message ?? '',
        status: 'done',
        expandable: false,
      }
    case 'step':
      return {
        id, ts, category: 'step',
        title: payload.message ?? payload.agent ?? 'Step',
        status: 'running',
      }
    case 'error':
      return {
        id, ts, category: 'error',
        title: payload.message ?? 'Error',
        status: 'error',
      }
    case 'done':
      return {
        id, ts, category: 'done',
        title: payload.summary ?? 'Task complete',
        status: 'done',
      }
    default:
      return null
  }
}

function toolLabel(tool: string): string {
  const map: Record<string, string> = {
    read_file:   'Reading',
    write_file:  'Writing',
    edit_file:   'Editing',
    create_file: 'Creating',
    list_files:  'Listing',
    search_code: 'Searching',
    run_command: 'Running',
    delete_file: 'Deleting',
  }
  return map[tool] ?? tool.replace('_', ' ')
}

function firstParam(params: Record<string, string> = {}): string {
  const v = Object.values(params)[0] ?? ''
  return v.length > 40 ? v.slice(0, 40) + '…' : v
}
