/**
 * useMemoryContext - React hook for conversation memory
 */

import { useState, useEffect, useCallback } from 'react'
import {
  MemoryContext,
  UserPreferences,
  getConversationMemory,
  updateConversationGoal,
  recordDecision,
  addOpenTask,
  getUserPreferences,
  updateUserPreferences,
} from '../api/memoryContext'

interface UseMemoryContextReturn {
  memory: MemoryContext | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
  setGoal: (goal: string) => Promise<void>
  recordDecision: (decision: string, context?: Record<string, any>) => Promise<void>
  addOpenTask: (title: string, description?: string) => Promise<void>
}

export function useMemoryContext(conversationId: string | null): UseMemoryContextReturn {
  const [memory, setMemory] = useState<MemoryContext | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!conversationId) {
      setMemory(null)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const data = await getConversationMemory(conversationId)
      setMemory(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load memory')
    } finally {
      setLoading(false)
    }
  }, [conversationId])

  useEffect(() => {
    refresh()
  }, [refresh])

  const setGoal = useCallback(async (goal: string) => {
    if (!conversationId) return
    await updateConversationGoal(conversationId, goal)
    await refresh()
  }, [conversationId, refresh])

  const recordDecisionCb = useCallback(async (decision: string, context?: Record<string, any>) => {
    if (!conversationId) return
    await recordDecision(conversationId, decision, context)
    await refresh()
  }, [conversationId, refresh])

  const addOpenTaskCb = useCallback(async (title: string, description?: string) => {
    if (!conversationId) return
    await addOpenTask(conversationId, title, description)
    await refresh()
  }, [conversationId, refresh])

  return {
    memory,
    loading,
    error,
    refresh,
    setGoal,
    recordDecision: recordDecisionCb,
    addOpenTask: addOpenTaskCb,
  }
}

interface UseUserPreferencesReturn {
  preferences: UserPreferences
  loading: boolean
  error: string | null
  update: (updates: Partial<UserPreferences>) => Promise<void>
  refresh: () => Promise<void>
}

export function useUserPreferences(): UseUserPreferencesReturn {
  const [preferences, setPreferences] = useState<UserPreferences>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getUserPreferences()
      setPreferences(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load preferences')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const update = useCallback(async (updates: Partial<UserPreferences>) => {
    await updateUserPreferences(updates)
    await refresh()
  }, [refresh])

  return {
    preferences,
    loading,
    error,
    update,
    refresh,
  }
}
