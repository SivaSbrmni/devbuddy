import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'

export interface Task {
  id: string
  tenant_id: string
  title: string
  description?: string
  state: string
  repo_id?: string
  branch?: string
  policy_profile: string
  iteration_count: number
  token_budget_used: number
  created_at: string
  updated_at: string
  completed_at?: string
  events?: TaskEvent[]
}

export interface TaskEvent {
  id: string
  task_id: string
  event_type: string
  from_state?: string
  to_state?: string
  actor_type: string
  actor_id?: string
  payload: Record<string, unknown>
  created_at: string
}

export function useTasks() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchTasks = useCallback(async () => {
    try {
      setLoading(true)
      const data = await api.get<Task[]>('/api/v1/tasks')
      setTasks(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load tasks')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchTasks() }, [fetchTasks])

  const createTask = async (payload: {
    title: string
    description?: string
    repo_id?: string
    branch?: string
    policy_profile?: string
  }) => {
    const task = await api.post<Task>('/api/v1/tasks', payload)
    setTasks(prev => [task, ...prev])
    return task
  }

  const transitionState = async (taskId: string, toState: string, reason?: string) => {
    const updated = await api.patch<Task>(`/api/v1/tasks/${taskId}/state`, { to_state: toState, reason })
    setTasks(prev => prev.map(t => t.id === taskId ? updated : t))
    return updated
  }

  return { tasks, loading, error, fetchTasks, createTask, transitionState }
}

export function useTask(taskId: string | undefined) {
  const [task, setTask] = useState<Task | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!taskId) return
    setLoading(true)
    api.get<Task>(`/api/v1/tasks/${taskId}`)
      .then(data => { setTask(data); setError(null) })
      .catch(e => setError(e instanceof Error ? e.message : 'Failed to load task'))
      .finally(() => setLoading(false))
  }, [taskId])

  return { task, loading, error, setTask }
}
