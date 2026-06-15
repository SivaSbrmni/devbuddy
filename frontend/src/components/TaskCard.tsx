/**
 * TaskCard — the core UI unit of DevBuddy's engineering console.
 *
 * Each user message becomes a TaskCard. The card streams child events
 * in real time: planning → reading → executing → testing → git → PR.
 *
 * Design principles:
 *  - Every second must increase user confidence
 *  - Show meaningful work, never "Loading…"
 *  - Events are expandable, indented, and timestamped
 *  - Progress bar animates live during execution
 */

import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import Icon from './Icon'

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
}

interface TaskCardProps {
  card: TaskCardData
  userAvatar?: string | null
  userName?: string
  isStreaming?: boolean
  onRetry?: () => void
}

// ── Config ───────────────────────────────────────────────────────────────────

const CATEGORY_CONFIG: Record<EventCategory, { icon: string; color: string; label: string }> = {
  plan:    { icon: '📋', color: '#818cf8', label: 'Planning'         },
  context: { icon: '📚', color: '#a78bfa', label: 'Repository'       },
  search:  { icon: '🔎', color: '#60a5fa', label: 'Searching'        },
  read:    { icon: '📁', color: '#93c5fd', label: 'Reading'          },
  analyze: { icon: '🏗', color: '#c084fc', label: 'Analyzing'        },
  execute: { icon: '🔧', color: '#34d399', label: 'Executing'        },
  test:    { icon: '🧪', color: '#fbbf24', label: 'Testing'          },
  reflect: { icon: '🔄', color: '#94a3b8', label: 'Reflecting'       },
  branch:  { icon: '🌿', color: '#4ade80', label: 'Branch'           },
  commit:  { icon: '💾', color: '#86efac', label: 'Commit'           },
  push:    { icon: '🚀', color: '#6ee7b7', label: 'Push'             },
  pr:      { icon: '🔗', color: '#818cf8', label: 'Pull Request'     },
  tool:    { icon: '⚡', color: '#f9a8d4', label: 'Tool'             },
  think:   { icon: '🧠', color: '#c4b5fd', label: 'Reasoning'        },
  observe: { icon: '👁', color: '#7dd3fc', label: 'Observed'         },
  warn:    { icon: '⚠️', color: '#fbbf24', label: 'Warning'          },
  error:   { icon: '✗',  color: '#ef4444', label: 'Error'            },
  done:    { icon: '✅', color: '#34d399', label: 'Complete'         },
  step:    { icon: '→',  color: '#94a3b8', label: 'Step'             },
}

function elapsed(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`
}

function liveElapsed(startedAt: number): string {
  const ms = Date.now() - startedAt
  if (ms < 60000) return `${Math.floor(ms / 1000)}s`
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`
}

// ── Sub-components ────────────────────────────────────────────────────────────

function EventRow({ event }: { event: TaskEvent }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = CATEGORY_CONFIG[event.category] ?? CATEGORY_CONFIG.step
  const isRunning = event.status === 'running'

  return (
    <div style={{ marginBottom: 2, animation: 'taskEventIn 0.18s ease' }}>
      <div
        onClick={() => event.expandable && setExpanded(x => !x)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '4px 8px',
          borderRadius: 6,
          cursor: event.expandable ? 'pointer' : 'default',
          background: isRunning ? 'rgba(99,102,241,0.05)' : 'transparent',
          transition: 'background 0.15s',
        }}
      >
        {/* Status dot */}
        <span style={{
          width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
          background: isRunning ? '#818cf8' :
            event.status === 'done' ? cfg.color :
            event.status === 'error' ? '#ef4444' :
            event.status === 'warn' ? '#fbbf24' : '#4b5563',
          animation: isRunning ? 'pulse 1.2s infinite' : 'none',
          boxShadow: isRunning ? `0 0 6px ${cfg.color}66` : 'none',
        }} />

        {/* Icon */}
        <span style={{ fontSize: 12, flexShrink: 0 }}>{cfg.icon}</span>

        {/* Title */}
        <span style={{
          fontSize: 12.5,
          color: isRunning ? '#e2e8f0' : event.status === 'error' ? '#ef4444' : event.status === 'warn' ? '#fbbf24' : '#94a3b8',
          fontWeight: isRunning ? 500 : 400,
          flex: 1,
          lineHeight: 1.4,
        }}>
          {event.title}
        </span>

        {/* Duration */}
        {event.durationMs !== undefined && (
          <span style={{ fontSize: 10, color: '#4b5563', fontFamily: 'monospace', flexShrink: 0 }}>
            {elapsed(event.durationMs)}
          </span>
        )}

        {/* Expand arrow */}
        {event.expandable && event.children && event.children.length > 0 && (
          <span style={{ fontSize: 10, color: '#4b5563', transition: 'transform 0.15s', transform: expanded ? 'rotate(90deg)' : 'rotate(0)' }}>▶</span>
        )}

        {/* Running spinner */}
        {isRunning && (
          <span style={{ fontSize: 10, color: cfg.color, animation: 'spin 1s linear infinite', flexShrink: 0 }}>◌</span>
        )}
      </div>

      {/* Expanded children */}
      {expanded && event.children && event.children.length > 0 && (
        <div style={{ marginLeft: 28, marginTop: 2, marginBottom: 4, padding: '6px 10px', background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 6 }}>
          {event.children.map((c, i) => (
            <div key={i} style={{ fontSize: 11.5, color: '#64748b', padding: '2px 0', fontFamily: event.category === 'read' || event.category === 'search' ? 'monospace' : 'inherit' }}>
              {c}
            </div>
          ))}
          {event.meta?.durationMs && (
            <div style={{ fontSize: 10, color: '#374151', marginTop: 4 }}>
              Execution time: {elapsed(event.meta.durationMs)}
            </div>
          )}
        </div>
      )}

      {/* Inline detail (no expand needed) */}
      {!event.expandable && event.detail && (
        <div style={{ marginLeft: 28, fontSize: 11, color: '#4b5563', padding: '1px 0' }}>{event.detail}</div>
      )}
    </div>
  )
}

function ProgressBar({ progress, status }: { progress: number; status: string }) {
  return (
    <div style={{ height: 2, background: 'rgba(255,255,255,0.06)', borderRadius: 1, overflow: 'hidden', marginBottom: 12 }}>
      <div style={{
        height: '100%',
        width: `${Math.max(2, progress)}%`,
        background: status === 'error' ? '#ef4444' : status === 'done' ? '#34d399' : 'linear-gradient(90deg, #6366f1, #818cf8)',
        transition: 'width 0.4s ease',
        borderRadius: 1,
        boxShadow: status !== 'error' && status !== 'done' ? '0 0 8px #6366f188' : 'none',
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
                  <span style={{ fontSize: 10 }}>⎇</span> {card.repo}
                </span>
              )}
              {card.branch && (
                <span style={{ fontSize: 11, color: '#4ade80', background: 'rgba(52,211,153,0.1)', padding: '2px 8px', borderRadius: 10, fontFamily: 'monospace' }}>
                  {card.branch.replace('devbuddy/', '')}
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
            <div style={{ padding: '10px 14px 8px', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.8px', flexShrink: 0 }}>
                    {isRunning ? 'Working' : card.status === 'error' ? 'Failed' : 'Complete'}
                  </span>
                  {isRunning && card.currentTool && (
                    <span style={{ fontSize: 11, color: '#818cf8', background: 'rgba(99,102,241,0.1)', padding: '1px 8px', borderRadius: 8, fontWeight: 500 }}>
                      {card.currentTool}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                  {card.status === 'running' && (
                    <span style={{ fontSize: 11, color: '#475569', fontFamily: 'monospace' }}>{elapsed2}</span>
                  )}
                  {card.status === 'done' && card.modifiedFiles && card.modifiedFiles.length > 0 && (
                    <span style={{ fontSize: 11, color: '#34d399' }}>{card.modifiedFiles.length} file{card.modifiedFiles.length !== 1 ? 's' : ''}</span>
                  )}
                </div>
              </div>

              {/* Progress bar */}
              {(isRunning || card.status === 'done' || card.status === 'error') && (
                <div style={{ marginTop: 8 }}>
                  <ProgressBar progress={card.progress} status={card.status} />
                </div>
              )}
            </div>

            {/* Events */}
            <div style={{ padding: '8px 10px', maxHeight: isRunning ? 340 : 280, overflowY: 'auto' }}>
              {card.events.map(evt => (
                <EventRow key={evt.id} event={evt} />
              ))}

              {/* Typing cursor when running */}
              {isRunning && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 8px', marginTop: 2 }}>
                  <div style={{ display: 'flex', gap: 3 }}>
                    {[0, 1, 2].map(i => (
                      <span key={i} style={{ width: 4, height: 4, borderRadius: '50%', background: '#6366f1', opacity: 0.7, animation: `pulse 1.2s ${i * 0.2}s infinite` }} />
                    ))}
                  </div>
                  <span style={{ fontSize: 11, color: '#475569' }}>
                    {card.currentTool || 'Processing…'}
                  </span>
                </div>
              )}
              <div ref={eventsEndRef} />
            </div>

            {/* PR / commit result bar */}
            {card.status === 'done' && (card.prUrl || card.commitHash) && (
              <div style={{ padding: '8px 14px', borderTop: '1px solid rgba(52,211,153,0.1)', background: 'rgba(52,211,153,0.04)', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                {card.prUrl && (
                  <a href={card.prUrl} target="_blank" rel="noopener noreferrer"
                    style={{ fontSize: 12, fontWeight: 700, color: 'white', background: 'linear-gradient(135deg, #6366f1, #818cf8)', padding: '5px 14px', borderRadius: 8, textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 5 }}>
                    🔗 View Pull Request {card.prNumber ? `#${card.prNumber}` : ''}
                  </a>
                )}
                {card.commitHash && (
                  <span style={{ fontSize: 11, color: '#34d399', fontFamily: 'monospace', background: 'rgba(52,211,153,0.1)', padding: '3px 8px', borderRadius: 6 }}>
                    {card.commitHash}
                  </span>
                )}
                {card.modifiedFiles && card.modifiedFiles.length > 0 && (
                  <span style={{ fontSize: 11, color: '#64748b' }}>
                    {card.modifiedFiles.slice(0, 3).join(', ')}{card.modifiedFiles.length > 3 ? ` +${card.modifiedFiles.length - 3} more` : ''}
                  </span>
                )}
              </div>
            )}

            {/* Error retry */}
            {card.status === 'error' && onRetry && (
              <div style={{ padding: '8px 14px', borderTop: '1px solid rgba(239,68,68,0.15)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <button onClick={onRetry} style={{ fontSize: 12, color: '#ef4444', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: '4px 12px', cursor: 'pointer' }}>
                  ↺ Retry
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
    read_file: '📁 Reading',
    write_file: '✏️ Writing',
    edit_file: '🔧 Editing',
    create_file: '🆕 Creating',
    list_files: '📂 Listing',
    search_code: '🔎 Searching',
    run_command: '⚡ Running',
    delete_file: '🗑 Deleting',
  }
  return map[tool] ?? `⚙ ${tool}`
}

function firstParam(params: Record<string, string> = {}): string {
  const v = Object.values(params)[0] ?? ''
  return v.length > 40 ? v.slice(0, 40) + '…' : v
}
