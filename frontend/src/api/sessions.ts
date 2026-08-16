/**
 * Agent Sessions API — Devin-style session management
 */

const API_BASE = import.meta.env.VITE_API_URL || ''
const API = `${API_BASE}/api/v1`

function getToken(): string {
  return localStorage.getItem('devbuddy_token') || ''
}

function authHeaders(): HeadersInit {
  const token = getToken()
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

export type SessionStatus =
  | 'queued' | 'planning' | 'running' | 'paused' | 'completed' | 'failed' | 'terminated'

export interface PlanStep {
  id: string
  title: string
  goal: string
  success_criteria?: string
  status: 'pending' | 'active' | 'completed' | 'failed' | 'skipped'
}

export interface SessionPlan {
  version: number
  summary: string
  steps: PlanStep[]
}

export interface SessionListItem {
  id: string
  title: string
  status: SessionStatus
  mode: string
  repository_name?: string | null
  pr_url?: string | null
  created_at: string
  updated_at: string
}

export interface AgentSession {
  id: string
  user_id: string
  conversation_id?: string | null
  title: string
  prompt: string
  mode: string
  status: SessionStatus
  repository_url?: string | null
  repository_owner?: string | null
  repository_name?: string | null
  branch?: string | null
  plan: SessionPlan | Record<string, unknown>
  current_step_index: number
  step_summaries: string[]
  devbox_type: string
  devbox_ref?: string | null
  github_run_id?: number | null
  github_run_url?: string | null
  pr_url?: string | null
  pr_number?: number | null
  result: Record<string, unknown>
  created_at: string
  updated_at: string
  completed_at?: string | null
}

export interface SessionEvent {
  type: string
  session_id: string
  seq: number
  timestamp: number
  payload: Record<string, unknown>
}

export interface CreateSessionRequest {
  prompt: string
  title?: string
  mode?: 'ask' | 'plan' | 'session'
  conversation_id?: string
  repository_owner?: string
  repository_name?: string
  repository_url?: string
  branch?: string
}

async function parseError(resp: Response, fallback: string): Promise<string> {
  const err = await resp.json().catch(() => ({}))
  const detail = err.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d: { msg?: string }) => d.msg || '').join(', ')
  return fallback
}

export async function createSession(req: CreateSessionRequest): Promise<AgentSession> {
  const token = getToken()
  const resp = await fetch(`${API}/sessions?token=${encodeURIComponent(token)}`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(req),
  })
  if (!resp.ok) {
    throw new Error(await parseError(resp, `Failed to create session (${resp.status})`))
  }
  return resp.json()
}

export async function getSession(sessionId: string): Promise<AgentSession> {
  const token = getToken()
  const resp = await fetch(
    `${API}/sessions/${sessionId}?token=${encodeURIComponent(token)}`,
    { headers: authHeaders() },
  )
  if (!resp.ok) {
    throw new Error(await parseError(resp, `Session not found (${resp.status})`))
  }
  return resp.json()
}

export async function listSessions(): Promise<SessionListItem[]> {
  const token = getToken()
  const resp = await fetch(`${API}/sessions?token=${encodeURIComponent(token)}`, {
    headers: authHeaders(),
  })
  if (!resp.ok) {
    throw new Error(await parseError(resp, `Failed to load sessions (${resp.status})`))
  }
  return resp.json()
}

export async function terminateSession(sessionId: string): Promise<void> {
  const token = getToken()
  const resp = await fetch(
    `${API}/sessions/${sessionId}/terminate?token=${encodeURIComponent(token)}`,
    { method: 'POST', headers: authHeaders() },
  )
  if (!resp.ok) {
    throw new Error(await parseError(resp, `Failed to terminate session (${resp.status})`))
  }
}

export async function sendSessionMessage(sessionId: string, content: string): Promise<void> {
  const token = getToken()
  const resp = await fetch(
    `${API}/sessions/${sessionId}/messages?token=${encodeURIComponent(token)}`,
    {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ content }),
    },
  )
  if (!resp.ok) {
    throw new Error(await parseError(resp, `Failed to send message (${resp.status})`))
  }
}

export function connectSessionStream(
  sessionId: string,
  onEvent: (event: SessionEvent) => void,
  getAfterSeq: () => number,
): () => void {
  let closed = false
  let es: EventSource | null = null
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  let retries = 0

  const connect = () => {
    if (closed) return
    const token = getToken()
    const afterSeq = getAfterSeq()
    const url = `${API}/sessions/${sessionId}/stream?token=${encodeURIComponent(token)}&after_seq=${afterSeq}`
    es = new EventSource(url)

    es.onmessage = (msg) => {
      retries = 0
      try {
        const event = JSON.parse(msg.data) as SessionEvent
        onEvent(event)
      } catch {
        /* ignore parse errors */
      }
    }

    es.onerror = () => {
      es?.close()
      if (!closed) {
        retries += 1
        const delay = Math.min(30000, 1000 * Math.pow(2, Math.min(retries, 5)))
        retryTimer = setTimeout(connect, delay)
      }
    }
  }

  connect()

  return () => {
    closed = true
    if (retryTimer) clearTimeout(retryTimer)
    es?.close()
  }
}
