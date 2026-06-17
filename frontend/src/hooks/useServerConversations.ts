/**
 * useServerConversations - React hook for server-side conversation management.
 * 
 * Replaces the localStorage-based useConversations() with server-side persistence,
 * enabling device-independent access and real-time synchronization.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Conversation,
  Message,
  CreateConversationRequest,
  CreateMessageRequest,
  listConversations,
  getConversation,
  createConversation as apiCreateConversation,
  updateConversation as apiUpdateConversation,
  deleteConversation as apiDeleteConversation,
  listMessages,
  createMessage as apiCreateMessage,
  syncConversations,
  conversationSSE,
  SSEMessage,
} from '../api/conversations'

interface UseServerConversationsOptions {
  autoSync?: boolean
  syncInterval?: number // ms
}

interface UseServerConversationsReturn {
  // State
  conversations: Conversation[]
  activeConversation: Conversation | null
  messages: Message[]
  loading: boolean
  error: string | null
  syncStatus: 'idle' | 'syncing' | 'error' | 'offline'
  lastSyncedAt: string | null
  isWebSocketConnected: boolean
  
  // Actions
  setActiveConversation: (id: string | null) => void
  createConversation: (req: CreateConversationRequest) => Promise<Conversation>
  updateConversation: (id: string, updates: Partial<Conversation>) => Promise<void>
  deleteConversation: (id: string) => Promise<void>
  createMessage: (conversationId: string, req: CreateMessageRequest) => Promise<Message>
  refreshMessages: (conversationId: string) => Promise<void>
  sync: () => Promise<void>
  forceRefresh: () => Promise<void>
}

// Cache for optimistic updates
interface OptimisticCache {
  conversations: Map<string, Conversation>
  messages: Map<string, Message[]>
}

export function useServerConversations(
  options: UseServerConversationsOptions = {}
): UseServerConversationsReturn {
  const { autoSync = true, syncInterval = 30000 } = options
  
  // State
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [syncStatus, setSyncStatus] = useState<UseServerConversationsReturn['syncStatus']>('idle')
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null)
  const [isWebSocketConnected, setIsWebSocketConnected] = useState(false)
  
  // Refs for sync logic
  const syncTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const isMountedRef = useRef(true)
  
  // Derived state
  const activeConversation = conversations.find(c => c.id === activeConversationId) || null
  
  // ─── Initial Load ─────────────────────────────────────────────────────────
  
  const loadConversations = useCallback(async () => {
    if (!isMountedRef.current) return
    
    setLoading(true)
    setError(null)
    
    try {
      const data = await listConversations({ limit: 100 })
      if (isMountedRef.current) {
        setConversations(data)
        setLastSyncedAt(new Date().toISOString())
        setSyncStatus('idle')
      }
    } catch (e) {
      if (isMountedRef.current) {
        setError(e instanceof Error ? e.message : 'Failed to load conversations')
        setSyncStatus('error')
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false)
      }
    }
  }, [])
  
  // Load on mount
  useEffect(() => {
    loadConversations()
    
    return () => {
      isMountedRef.current = false
      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current)
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [loadConversations])
  
  // ─── SSE Real-Time Updates ────────────────────────────────────────────────
  
  useEffect(() => {
    // Connect SSE
    conversationSSE.connect()
    
    // Handle messages
    const unsubscribeMessage = conversationSSE.onMessage((msg: SSEMessage) => {
      switch (msg.type) {
        case 'conversation_updated':
          setConversations(prev => {
            const exists = prev.find(c => c.id === msg.conversation.id)
            if (exists) {
              return prev.map(c => c.id === msg.conversation.id ? msg.conversation : c)
            }
            return [msg.conversation, ...prev]
          })
          break
          
        case 'message_created':
          if (msg.conversation_id === activeConversationId) {
            setMessages(prev => {
              if (prev.find(m => m.id === msg.message.id)) return prev
              return [...prev, msg.message]
            })
          }
          // Update conversation last_message_at
          setConversations(prev =>
            prev.map(c =>
              c.id === msg.conversation_id
                ? { ...c, last_message_at: msg.message.created_at, message_count: c.message_count + 1 }
                : c
            )
          )
          break
          
        case 'sync_required':
          sync()
          break
      }
    })
    
    // Handle connection state
    const unsubscribeConnect = conversationSSE.onConnect(() => {
      setIsWebSocketConnected(true)
      setSyncStatus('idle')
    })
    
    const unsubscribeDisconnect = conversationSSE.onDisconnect(() => {
      setIsWebSocketConnected(false)
      setSyncStatus('offline')
    })
    
    return () => {
      unsubscribeMessage()
      unsubscribeConnect()
      unsubscribeDisconnect()
      conversationSSE.disconnect()
    }
  }, [activeConversationId])
  
  // ─── Periodic Sync ────────────────────────────────────────────────────────
  
  const sync = useCallback(async () => {
    if (!isMountedRef.current) return
    
    setSyncStatus('syncing')
    
    try {
      const req = {
        last_sync_at: lastSyncedAt || undefined,
        client_conversations: conversations.map(c => ({
          id: c.id,
          updated_at: c.updated_at,
          version: 0, // TODO: Add version field
        })),
      }
      
      const response = await syncConversations(req)
      
      if (!isMountedRef.current) return
      
      // Merge server updates
      if (response.updated_conversations.length > 0) {
        setConversations(prev => {
          const updatedIds = new Set(response.updated_conversations.map(c => c.id))
          const unchanged = prev.filter(c => !updatedIds.has(c.id))
          return [...response.updated_conversations, ...unchanged].sort(
            (a, b) => new Date(b.last_message_at || b.created_at).getTime() -
                      new Date(a.last_message_at || a.created_at).getTime()
          )
        })
      }
      
      // Remove deleted conversations
      if (response.deleted_ids.length > 0) {
        setConversations(prev => prev.filter(c => !response.deleted_ids.includes(c.id)))
      }
      
      setLastSyncedAt(response.server_timestamp)
      setSyncStatus('idle')
    } catch (e) {
      if (isMountedRef.current) {
        setSyncStatus('error')
      }
    }
  }, [conversations, lastSyncedAt])
  
  useEffect(() => {
    if (!autoSync) return
    
    const scheduleSync = () => {
      syncTimeoutRef.current = setTimeout(() => {
        sync()
        scheduleSync()
      }, syncInterval)
    }
    
    scheduleSync()
    
    return () => {
      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current)
      }
    }
  }, [autoSync, syncInterval, sync])
  
  // ─── Actions ──────────────────────────────────────────────────────────────
  
  const setActiveConversation = useCallback(async (id: string | null) => {
    setActiveConversationId(id)
    setMessages([])
    
    if (id) {
      try {
        const msgs = await listMessages(id, { limit: 100 })
        if (isMountedRef.current) {
          setMessages(msgs)
        }
      } catch (e) {
        console.error('Failed to load messages:', e)
      }
    }
  }, [])
  
  const createConversation = useCallback(async (req: CreateConversationRequest) => {
    const conversation = await apiCreateConversation(req)
    
    if (isMountedRef.current) {
      setConversations(prev => [conversation, ...prev])
      setActiveConversationId(conversation.id)
    }
    
    return conversation
  }, [])
  
  const updateConversation = useCallback(async (id: string, updates: Partial<Pick<Conversation, 'title' | 'status' | 'summary' | 'current_goal'>>) => {
    // Optimistic update
    setConversations(prev =>
      prev.map(c => c.id === id ? { ...c, ...updates, updated_at: new Date().toISOString() } : c)
    )
    
    try {
      await apiUpdateConversation(id, updates)
      // Server will broadcast via WebSocket, which will update state
    } catch (e) {
      // Revert on error
      loadConversations()
      throw e
    }
  }, [loadConversations])
  
  const deleteConversation = useCallback(async (id: string) => {
    // Optimistic update
    setConversations(prev => prev.filter(c => c.id !== id))
    
    if (activeConversationId === id) {
      setActiveConversationId(null)
      setMessages([])
    }
    
    try {
      await apiDeleteConversation(id)
    } catch (e) {
      // Revert on error
      loadConversations()
      throw e
    }
  }, [activeConversationId, loadConversations])
  
  const createMessage = useCallback(async (conversationId: string, req: CreateMessageRequest) => {
    // Optimistic update for UI responsiveness
    const optimisticMessage: Message = {
      id: `temp-${Date.now()}`,
      conversation_id: conversationId,
      role: req.role,
      content: req.content,
      metadata: req.metadata || {},
      is_complete: true,
      created_at: new Date().toISOString(),
    }
    
    if (conversationId === activeConversationId) {
      setMessages(prev => [...prev, optimisticMessage])
    }
    
    try {
      const message = await apiCreateMessage(conversationId, req)
      
      if (isMountedRef.current) {
        // Replace optimistic message with real one
        if (conversationId === activeConversationId) {
          setMessages(prev => prev.map(m => m.id === optimisticMessage.id ? message : m))
        }
        
        // Update conversation in list
        setConversations(prev =>
          prev.map(c =>
            c.id === conversationId
              ? { ...c, last_message_at: message.created_at, message_count: c.message_count + 1 }
              : c
          )
        )
      }
      
      return message
    } catch (e) {
      // Remove optimistic message on error
      if (conversationId === activeConversationId) {
        setMessages(prev => prev.filter(m => m.id !== optimisticMessage.id))
      }
      throw e
    }
  }, [activeConversationId])
  
  const refreshMessages = useCallback(async (conversationId: string) => {
    const msgs = await listMessages(conversationId, { limit: 100 })
    if (isMountedRef.current && conversationId === activeConversationId) {
      setMessages(msgs)
    }
  }, [activeConversationId])
  
  const forceRefresh = useCallback(async () => {
    await loadConversations()
    if (activeConversationId) {
      await refreshMessages(activeConversationId)
    }
  }, [loadConversations, activeConversationId, refreshMessages])
  
  return {
    conversations,
    activeConversation,
    messages,
    loading,
    error,
    syncStatus,
    lastSyncedAt,
    isWebSocketConnected,
    setActiveConversation,
    createConversation,
    updateConversation,
    deleteConversation,
    createMessage,
    refreshMessages,
    sync,
    forceRefresh,
  }
}

// Hook for a single conversation (lighter weight)
export function useConversation(id: string | null) {
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  useEffect(() => {
    if (!id) {
      setConversation(null)
      setMessages([])
      return
    }
    
    let isMounted = true
    
    const load = async () => {
      setLoading(true)
      try {
        const [convData, msgsData] = await Promise.all([
          getConversation(id, { include_messages: false }),
          listMessages(id),
        ])
        if (isMounted) {
          setConversation(convData)
          setMessages(msgsData)
        }
      } catch (e) {
        if (isMounted) {
          setError(e instanceof Error ? e.message : 'Failed to load')
        }
      } finally {
        if (isMounted) {
          setLoading(false)
        }
      }
    }
    
    load()
    
    // Subscribe to SSE updates
    const unsubscribe = conversationSSE.onMessage((msg: SSEMessage) => {
      if (!isMounted) return
      
      switch (msg.type) {
        case 'conversation_updated':
          if (msg.conversation.id === id) {
            setConversation(msg.conversation)
          }
          break
        case 'message_created':
          if (msg.conversation_id === id) {
            setMessages(prev => [...prev, msg.message])
          }
          break
      }
    })
    
    return () => {
      isMounted = false
      unsubscribe()
    }
  }, [id])
  
  const addMessage = useCallback(async (req: CreateMessageRequest) => {
    if (!id) return null
    const message = await apiCreateMessage(id, req)
    setMessages(prev => [...prev, message])
    return message
  }, [id])
  
  return {
    conversation,
    messages,
    loading,
    error,
    addMessage,
  }
}
