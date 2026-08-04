import { useCallback, useEffect, useState } from 'react'
import { SessionListItem, listSessions } from '../api/sessions'

export function useSessionList(pollIntervalMs = 15000) {
  const [sessions, setSessions] = useState<SessionListItem[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const data = await listSessions()
      setSessions(data)
    } catch {
      /* keep previous list */
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, pollIntervalMs)
    return () => clearInterval(id)
  }, [refresh, pollIntervalMs])

  return { sessions, loading, refresh }
}
