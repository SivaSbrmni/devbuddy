import { useState, useEffect, useRef, useCallback } from 'react'
import { getWsUrl } from '@/lib/api'

interface WsEvent {
  type: string
  task_id: string
  timestamp: string
  event: Record<string, unknown>
}

export function useTaskStream(taskId: string | undefined) {
  const [events, setEvents] = useState<WsEvent[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  const connect = useCallback(async () => {
    if (!taskId) return
    if (wsRef.current) wsRef.current.close()

    const url = await getWsUrl(taskId)
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)
    ws.onmessage = (e) => {
      try {
        const parsed: WsEvent = JSON.parse(e.data)
        if (parsed.type !== 'PING') {
          setEvents(prev => [...prev.slice(-99), parsed])
        }
      } catch { /* ignore malformed */ }
    }
  }, [taskId])

  useEffect(() => {
    connect()
    return () => { wsRef.current?.close() }
  }, [connect])

  return { events, connected }
}
