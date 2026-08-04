/**
 * useSession — live session state with SSE event stream
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AgentSession,
  SessionEvent,
  connectSessionStream,
  getSession,
  sendSessionMessage,
  terminateSession,
} from '../api/sessions'

export interface ShellEntry {
  id: string
  command: string
  output: string
  exitCode: number
  ts: number
}

export interface FileChange {
  path: string
  action: string
  diff?: string
  ts: number
}

export interface ThinkingEntry {
  id: string
  content: string
  phase?: string
  ts: number
}

export interface SessionUIState {
  session: AgentSession | null
  loading: boolean
  error: string | null
  events: SessionEvent[]
  shellEntries: ShellEntry[]
  fileChanges: FileChange[]
  thinkingLog: ThinkingEntry[]
  plan: Record<string, unknown> | null
  prUrl: string | null
  devboxMessage: string
  streamingContent: string
}

export function useSession(sessionId: string) {
  const [state, setState] = useState<SessionUIState>({
    session: null,
    loading: true,
    error: null,
    events: [],
    shellEntries: [],
    fileChanges: [],
    thinkingLog: [],
    plan: null,
    prUrl: null,
    devboxMessage: '',
    streamingContent: '',
  })

  const lastSeqRef = useRef(0)
  const disconnectRef = useRef<(() => void) | null>(null)

  const applyEvent = useCallback((event: SessionEvent) => {
    lastSeqRef.current = Math.max(lastSeqRef.current, event.seq)

    setState(prev => {
      const next = { ...prev, events: [...prev.events, event] }

      switch (event.type) {
        case 'plan_updated':
          next.plan = event.payload.plan as Record<string, unknown>
          break
        case 'shell': {
          const entry: ShellEntry = {
            id: `${event.seq}`,
            command: String(event.payload.command || ''),
            output: String(event.payload.output || ''),
            exitCode: Number(event.payload.exit_code ?? 0),
            ts: event.timestamp,
          }
          next.shellEntries = [...prev.shellEntries, entry]
          break
        }
        case 'file_change': {
          next.fileChanges = [...prev.fileChanges, {
            path: String(event.payload.path || ''),
            action: String(event.payload.action || 'modified'),
            diff: event.payload.diff ? String(event.payload.diff) : undefined,
            ts: event.timestamp,
          }]
          break
        }
        case 'thinking': {
          const streaming = Boolean(event.payload.streaming)
          const content = String(event.payload.content || '')
          if (streaming && event.payload.final !== true) {
            next.streamingContent = prev.streamingContent + content
          } else if (event.payload.final === true) {
            next.streamingContent = content
            next.thinkingLog = [...prev.thinkingLog, {
              id: `${event.seq}`,
              content,
              ts: event.timestamp,
            }]
          } else {
            next.thinkingLog = [...prev.thinkingLog, {
              id: `${event.seq}`,
              content,
              phase: event.payload.phase ? String(event.payload.phase) : undefined,
              ts: event.timestamp,
            }]
          }
          break
        }
        case 'pr_created':
          next.prUrl = String(event.payload.url || '')
          break
        case 'devbox_status':
          next.devboxMessage = String(event.payload.message || event.payload.state || '')
          break
        case 'session_status':
          if (prev.session) {
            next.session = {
              ...prev.session,
              status: String(event.payload.status || prev.session.status) as AgentSession['status'],
            }
          }
          break
        case 'error':
          next.error = String(event.payload.message || 'Unknown error')
          break
      }

      return next
    })
  }, [])

  const refresh = useCallback(async () => {
    try {
      const session = await getSession(sessionId)
      setState(prev => ({
        ...prev,
        session,
        loading: false,
        plan: (session.plan as Record<string, unknown>) || prev.plan,
        prUrl: session.pr_url || prev.prUrl,
      }))
    } catch (e) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: e instanceof Error ? e.message : 'Failed to load session',
      }))
    }
  }, [sessionId])

  useEffect(() => {
    refresh()
    disconnectRef.current = connectSessionStream(sessionId, applyEvent, lastSeqRef.current)
    return () => {
      disconnectRef.current?.()
    }
  }, [sessionId, applyEvent, refresh])

  const terminate = useCallback(async () => {
    await terminateSession(sessionId)
    await refresh()
  }, [sessionId, refresh])

  const sendMessage = useCallback(async (content: string) => {
    await sendSessionMessage(sessionId, content)
    setState(prev => ({
      ...prev,
      thinkingLog: [...prev.thinkingLog, {
        id: `followup-${Date.now()}`,
        content: `You: ${content}`,
        phase: 'follow-up',
        ts: Date.now(),
      }],
    }))
    await refresh()
  }, [sessionId, refresh])

  return { ...state, refresh, terminate, sendMessage }
}
