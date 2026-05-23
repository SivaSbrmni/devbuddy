import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { DEV_TOKEN_KEY } from '@/lib/api'
import {
  Send, Bot, User, Loader2, CheckCircle2, Circle,
  Sparkles, ChevronRight, ExternalLink, AlertCircle,
  Code2, Bug, Zap, RefreshCw, Eye, Rocket, Search,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const INTENT_ICONS: Record<string, React.ElementType> = {
  code_change: Code2,
  feature: Sparkles,
  bug_fix: Bug,
  refactor: RefreshCw,
  review: Eye,
  deploy: Rocket,
  query: Search,
  unknown: Zap,
}

const STAGE_ORDER = [
  'PENDING', 'PLANNING', 'EXECUTING', 'VALIDATING',
  'SECURITY_REVIEW', 'READY_TO_PUSH', 'COMPLETED',
]

type MessageRole = 'user' | 'assistant' | 'system'

interface IntentData {
  intent: string
  confidence: number
  title: string
  description: string
  reasoning: string
  steps: string[]
  repo_id: string | null
  branch: string | null
  policy_profile: string
}

interface AgentStage {
  stage: string
  state: string
  message: string
  done: boolean
}

interface ChatMessage {
  id: string
  role: MessageRole
  text?: string
  intent?: IntentData
  taskId?: string
  taskTitle?: string
  stages?: AgentStage[]
  finalState?: string
  error?: string
  streaming?: boolean
}

const SUGGESTIONS = [
  'Add rate limiting middleware to the authentication service',
  'Fix the memory leak in the background job processor',
  'Refactor the user onboarding flow to use async/await',
  'Add OpenTelemetry tracing to all API endpoints',
  'Review and harden the SQL query builder for injection risks',
]

function IntentCard({ intent }: { intent: IntentData }) {
  const Icon = INTENT_ICONS[intent.intent] ?? Zap
  const pct = Math.round(intent.confidence * 100)
  return (
    <div className="mt-2 rounded-xl border border-primary/20 bg-primary/5 p-4 space-y-3">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center shrink-0">
          <Icon className="w-4 h-4 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-foreground truncate">{intent.title}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[10px] uppercase tracking-wide text-primary font-medium bg-primary/10 px-1.5 py-0.5 rounded">
              {intent.intent.replace('_', ' ')}
            </span>
            <span className="text-[10px] text-muted-foreground">{pct}% confidence</span>
            <span className="text-[10px] text-muted-foreground">·</span>
            <span className="text-[10px] text-muted-foreground">{intent.policy_profile} policy</span>
          </div>
        </div>
      </div>

      <p className="text-xs text-muted-foreground leading-relaxed">{intent.reasoning}</p>

      {intent.steps.length > 0 && (
        <div className="space-y-1">
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium">Execution Plan</p>
          {intent.steps.map((s, i) => (
            <div key={i} className="flex items-start gap-2">
              <span className="text-[10px] font-mono text-primary mt-0.5 w-4 shrink-0">{i + 1}.</span>
              <span className="text-xs text-foreground/80">{s}</span>
            </div>
          ))}
        </div>
      )}

      {(intent.repo_id || intent.branch) && (
        <div className="flex items-center gap-3 pt-1 border-t border-primary/10">
          {intent.repo_id && (
            <span className="text-[10px] text-muted-foreground font-mono">{intent.repo_id}</span>
          )}
          {intent.branch && (
            <span className="text-[10px] text-muted-foreground font-mono">@ {intent.branch}</span>
          )}
        </div>
      )}
    </div>
  )
}

function AgentTimeline({
  stages, taskId, finalState,
}: { stages: AgentStage[]; taskId?: string; finalState?: string }) {
  const navigate = useNavigate()
  const done = finalState === 'COMPLETED'
  const failed = finalState === 'FAILED' || finalState === 'QUARANTINED'

  return (
    <div className="mt-3 rounded-xl border border-border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-foreground">Agent Execution</p>
        {taskId && (
          <button
            onClick={() => navigate(`/tasks/${taskId}`)}
            className="flex items-center gap-1 text-[10px] text-primary hover:underline"
          >
            View task <ExternalLink className="w-2.5 h-2.5" />
          </button>
        )}
      </div>

      <div className="space-y-2">
        {STAGE_ORDER.slice(1).map((s) => {
          const match = stages.find(st => st.state === s)
          const isDone = !!match?.done
          const isActive = stages.length > 0 && stages[stages.length - 1].state === s && !isDone
          return (
            <div key={s} className="flex items-start gap-2.5">
              <div className="mt-0.5 shrink-0">
                {isDone ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                ) : isActive ? (
                  <Loader2 className="w-3.5 h-3.5 text-primary animate-spin" />
                ) : (
                  <Circle className="w-3.5 h-3.5 text-muted-foreground/30" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className={cn(
                  'text-xs font-medium',
                  isDone ? 'text-foreground' : isActive ? 'text-primary' : 'text-muted-foreground/50'
                )}>
                  {s.replace(/_/g, ' ')}
                </p>
                {(isDone || isActive) && match?.message && (
                  <p className="text-[10px] text-muted-foreground mt-0.5 leading-relaxed">{match.message}</p>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {done && (
        <div className="flex items-center gap-2 pt-2 border-t border-border">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <p className="text-xs text-emerald-400 font-medium">All stages completed successfully</p>
        </div>
      )}
      {failed && (
        <div className="flex items-center gap-2 pt-2 border-t border-border">
          <AlertCircle className="w-4 h-4 text-destructive shrink-0" />
          <p className="text-xs text-destructive font-medium">Task {finalState?.toLowerCase()}</p>
        </div>
      )}
    </div>
  )
}

function Message({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user'
  return (
    <div className={cn('flex gap-3', isUser ? 'flex-row-reverse' : 'flex-row')}>
      <div className={cn(
        'w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5',
        isUser ? 'bg-primary/20' : 'bg-primary/10 border border-primary/20'
      )}>
        {isUser
          ? <User className="w-3.5 h-3.5 text-primary" />
          : <Bot className="w-3.5 h-3.5 text-primary" />}
      </div>

      <div className={cn('flex flex-col gap-1 max-w-[80%]', isUser ? 'items-end' : 'items-start')}>
        {msg.text && (
          <div className={cn(
            'rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
            isUser
              ? 'bg-primary text-primary-foreground rounded-tr-sm'
              : 'bg-card border border-border text-foreground rounded-tl-sm'
          )}>
            {msg.streaming
              ? <span>{msg.text}<span className="inline-block w-1.5 h-3.5 bg-primary/60 ml-0.5 animate-pulse rounded-sm" /></span>
              : msg.text}
          </div>
        )}

        {msg.error && (
          <div className="rounded-2xl px-4 py-2.5 bg-destructive/10 border border-destructive/20 text-sm text-destructive rounded-tl-sm">
            {msg.error}
          </div>
        )}

        {msg.intent && <IntentCard intent={msg.intent} />}

        {(msg.stages !== undefined || msg.taskId) && (
          <AgentTimeline
            stages={msg.stages ?? []}
            taskId={msg.taskId}
            finalState={msg.finalState}
          />
        )}
      </div>
    </div>
  )
}

export function ChatPage() {
  const { user } = useAuth()
  const [messages, setMessages] = useState<ChatMessage[]>([{
    id: 'welcome',
    role: 'assistant',
    text: `Hi${user?.email ? ` ${user.email.split('@')[0]}` : ''}! I'm DevBuddy, your enterprise coding agent. Describe what you need — I'll analyze your intent, plan the work, and execute it autonomously through our secure pipeline.`,
  }])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const updateMsg = useCallback((id: string, patch: Partial<ChatMessage>) => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, ...patch } : m))
  }, [])

  const send = useCallback(async (text: string) => {
    if (!text.trim() || busy) return
    setBusy(true)

    const userMsgId = `u-${Date.now()}`
    const asstMsgId = `a-${Date.now()}`

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', text: text.trim() },
      { id: asstMsgId, role: 'assistant', text: 'Analyzing your request...', streaming: true },
    ])
    setInput('')

    try {
      const token = localStorage.getItem(DEV_TOKEN_KEY)
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const resp = await fetch(`${API_BASE}/api/v1/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ message: text.trim() }),
      })

      if (!resp.ok) throw new Error(`Server error ${resp.status}`)

      const reader = resp.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let stages: AgentStage[] = []
      let taskId: string | undefined
      let taskTitle: string | undefined

      updateMsg(asstMsgId, { text: '', streaming: false })

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''

        for (const part of parts) {
          const lines = part.split('\n')
          const eventLine = lines.find(l => l.startsWith('event:'))
          const dataLine = lines.find(l => l.startsWith('data:'))
          if (!eventLine || !dataLine) continue

          const eventType = eventLine.replace('event:', '').trim()
          const payload = JSON.parse(dataLine.replace('data:', '').trim())

          if (eventType === 'status') {
            updateMsg(asstMsgId, { text: payload.message, streaming: true })
          }

          if (eventType === 'intent') {
            updateMsg(asstMsgId, {
              text: `Intent identified: **${payload.intent.replace('_', ' ')}** (${Math.round(payload.confidence * 100)}% confidence)`,
              streaming: false,
              intent: payload,
            })
          }

          if (eventType === 'task_created') {
            taskId = payload.task_id
            taskTitle = payload.title
            stages = []
            updateMsg(asstMsgId, {
              taskId,
              taskTitle,
              stages,
              text: `Task created — starting autonomous execution pipeline...`,
            })
          }

          if (eventType === 'agent_stage') {
            stages = [...stages, { stage: payload.stage, state: payload.state, message: payload.message, done: false }]
            updateMsg(asstMsgId, { stages: [...stages] })
          }

          if (eventType === 'state_update') {
            stages = stages.map(s =>
              s.state === payload.state ? { ...s, done: true } : s
            )
            updateMsg(asstMsgId, { stages: [...stages] })
          }

          if (eventType === 'done') {
            stages = stages.map(s => ({ ...s, done: true }))
            updateMsg(asstMsgId, {
              stages: [...stages],
              finalState: payload.final_state,
              text: `Task completed successfully through all pipeline stages.`,
              streaming: false,
            })
          }
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      updateMsg(asstMsgId, { text: undefined, error: `Failed: ${msg}`, streaming: false })
    } finally {
      setBusy(false)
      inputRef.current?.focus()
    }
  }, [busy, updateMsg])

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="border-b border-border px-6 py-3 flex items-center gap-3 bg-card shrink-0">
        <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
          <Bot className="w-4 h-4 text-primary" />
        </div>
        <div>
          <p className="text-sm font-semibold text-foreground">DevBuddy Agent</p>
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[10px] text-muted-foreground">Connected · llama3.2 · enterprise pipeline</span>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {messages.map(msg => <Message key={msg.id} msg={msg} />)}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Suggestions */}
      {messages.length === 1 && !busy && (
        <div className="px-4 pb-3">
          <div className="max-w-3xl mx-auto">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-2 ml-1">Try asking</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map(s => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-xs text-muted-foreground border border-border rounded-lg px-3 py-1.5 hover:border-primary/40 hover:text-foreground hover:bg-primary/5 transition-colors flex items-center gap-1.5"
                >
                  <ChevronRight className="w-3 h-3" />
                  {s}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Input */}
      <div className="border-t border-border px-4 py-4 bg-card shrink-0">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-end gap-3 rounded-xl border border-border bg-background focus-within:border-primary/50 focus-within:ring-1 focus-within:ring-primary/20 transition-all px-4 py-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Describe what you need — fix a bug, add a feature, refactor code..."
              disabled={busy}
              rows={1}
              className="flex-1 resize-none bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-50 max-h-32 leading-relaxed"
              style={{ height: 'auto' }}
              onInput={e => {
                const t = e.currentTarget
                t.style.height = 'auto'
                t.style.height = `${Math.min(t.scrollHeight, 128)}px`
              }}
            />
            <button
              onClick={() => send(input)}
              disabled={busy || !input.trim()}
              className={cn(
                'w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-all',
                input.trim() && !busy
                  ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                  : 'bg-muted text-muted-foreground cursor-not-allowed'
              )}
            >
              {busy
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : <Send className="w-3.5 h-3.5" />}
            </button>
          </div>
          <p className="text-[10px] text-muted-foreground text-center mt-2">
            Enter to send · Shift+Enter for new line · All actions are audited
          </p>
        </div>
      </div>
    </div>
  )
}
