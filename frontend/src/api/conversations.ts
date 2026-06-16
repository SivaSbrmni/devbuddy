/**
 * Conversation API client - server-side persistence replacing localStorage.
 * 
 * This module provides typed API calls for the conversation endpoints,
 * enabling device-independent access and real-time synchronization.
 */

const API = `${import.meta.env.VITE_API_URL || ''}/api/v1`

export interface Conversation {
  id: string
  user_id: string
  title: string
  repository_url: string | null
  repository_name: string | null
  repository_owner: string | null
  branch: string | null
  summary: string
  current_goal: string
  completed_tasks: any[]
  open_tasks: any[]
  modified_files: string[]
  important_decisions: any[]
  status: 'active' | 'archived' | 'completed'
  last_message_at: string | null
  message_count: number
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  metadata: {
    task_id?: string
    run_id?: string
    tool_calls?: any[]
    files?: any[]
    steps?: string[]
    task_card?: any
  }
  is_complete: boolean
  created_at: string
}

export interface CreateConversationRequest {
  title?: string
  repository_url?: string
  repository_name?: string
  repository_owner?: string
  branch?: string
}

export interface CreateMessageRequest {
  role: 'user' | 'assistant' | 'system'
  content: string
  metadata?: Record<string, any>
}

export interface SyncRequest {
  last_sync_at?: string
  client_conversations: Array<{
    id: string
    updated_at: string
    version: number
  }>
}

export interface SyncResponse {
  updated_conversations: Conversation[]
  deleted_ids: string[]
  server_timestamp: string
}

// ─── API Functions ──────────────────────────────────────────────────────────

function getToken(): string {
  return localStorage.getItem('devbuddy_token') || ''
}

async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken()
  if (!token) {
    throw new Error('Not authenticated')
  }
  
  const separator = url.includes('?') ? '&' : '?'
  const authedUrl = `${url}${separator}token=${encodeURIComponent(token)}`
  
  return fetch(authedUrl, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
}

export async function listConversations(
  options: { status?: string; repo_url?: string; limit?: number; offset?: number } = {}
): Promise<Conversation[]> {
  const params = new URLSearchParams()
  if (options.status) params.set('status', options.status)
  if (options.repo_url) params.set('repo_url', options.repo_url)
  if (options.limit) params.set('limit', String(options.limit))
  if (options.offset) params.set('offset', String(options.offset))
  
  const response = await fetchWithAuth(`${API}/conversations?${params}`)
  if (!response.ok) {
    throw new Error(`Failed to list conversations: ${response.status}`)
  }
  return response.json()
}

export async function getConversation(
  id: string,
  options: { include_messages?: boolean } = {}
): Promise<Conversation & { messages?: Message[] }> {
  const params = new URLSearchParams()
  if (options.include_messages !== false) params.set('include_messages', 'true')
  
  const response = await fetchWithAuth(`${API}/conversations/${id}?${params}`)
  if (!response.ok) {
    throw new Error(`Failed to get conversation: ${response.status}`)
  }
  return response.json()
}

export async function createConversation(
  req: CreateConversationRequest
): Promise<Conversation> {
  const response = await fetchWithAuth(`${API}/conversations`, {
    method: 'POST',
    body: JSON.stringify(req),
  })
  if (!response.ok) {
    throw new Error(`Failed to create conversation: ${response.status}`)
  }
  return response.json()
}

export async function updateConversation(
  id: string,
  updates: Partial<CreateConversationRequest> & { status?: string; summary?: string; current_goal?: string }
): Promise<Conversation> {
  const response = await fetchWithAuth(`${API}/conversations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  })
  if (!response.ok) {
    throw new Error(`Failed to update conversation: ${response.status}`)
  }
  return response.json()
}

export async function deleteConversation(id: string): Promise<void> {
  const response = await fetchWithAuth(`${API}/conversations/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete conversation: ${response.status}`)
  }
}

export async function listMessages(
  conversationId: string,
  options: { limit?: number; offset?: number } = {}
): Promise<Message[]> {
  const params = new URLSearchParams()
  if (options.limit) params.set('limit', String(options.limit))
  if (options.offset) params.set('offset', String(options.offset))
  
  const response = await fetchWithAuth(`${API}/conversations/${conversationId}/messages?${params}`)
  if (!response.ok) {
    throw new Error(`Failed to list messages: ${response.status}`)
  }
  return response.json()
}

export async function createMessage(
  conversationId: string,
  req: CreateMessageRequest
): Promise<Message> {
  const response = await fetchWithAuth(`${API}/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify(req),
  })
  if (!response.ok) {
    throw new Error(`Failed to create message: ${response.status}`)
  }
  return response.json()
}

export async function syncConversations(req: SyncRequest): Promise<SyncResponse> {
  const response = await fetchWithAuth(`${API}/conversations/sync`, {
    method: 'POST',
    body: JSON.stringify(req),
  })
  if (!response.ok) {
    throw new Error(`Failed to sync: ${response.status}`)
  }
  return response.json()
}

// ─── WebSocket ─────────────────────────────────────────────────────────────

export type WebSocketMessage =
  | { type: 'ping' }
  | { type: 'pong' }
  | { type: 'conversation_updated'; conversation: Conversation }
  | { type: 'message_created'; conversation_id: string; message: Message }
  | { type: 'sync_required' }

export class ConversationWebSocket {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private listeners: Array<(msg: WebSocketMessage) => void> = []
  private onConnectCallbacks: Array<() => void> = []
  private onDisconnectCallbacks: Array<() => void> = []

  connect(): void {
    const token = getToken()
    if (!token) {
      console.error('Cannot connect WebSocket: no token')
      return
    }

    const wsUrl = `${API.replace(/^http/, 'ws')}/conversations/ws?token=${encodeURIComponent(token)}`
    
    this.ws = new WebSocket(wsUrl)
    
    this.ws.onopen = () => {
      console.log('WebSocket connected')
      this.reconnectAttempts = 0
      this.onConnectCallbacks.forEach(cb => cb())
    }
    
    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WebSocketMessage
        this.listeners.forEach(cb => cb(msg))
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }
    
    this.ws.onclose = () => {
      console.log('WebSocket disconnected')
      this.onDisconnectCallbacks.forEach(cb => cb())
      this.attemptReconnect()
    }
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max WebSocket reconnect attempts reached')
      return
    }
    
    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
    
    console.log(`Reconnecting in ${delay}ms... (attempt ${this.reconnectAttempts})`)
    setTimeout(() => this.connect(), delay)
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  send(msg: WebSocketMessage): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg))
    }
  }

  ping(): void {
    this.send({ type: 'ping' })
  }

  onMessage(callback: (msg: WebSocketMessage) => void): () => void {
    this.listeners.push(callback)
    return () => {
      const index = this.listeners.indexOf(callback)
      if (index > -1) {
        this.listeners.splice(index, 1)
      }
    }
  }

  onConnect(callback: () => void): () => void {
    this.onConnectCallbacks.push(callback)
    return () => {
      const index = this.onConnectCallbacks.indexOf(callback)
      if (index > -1) {
        this.onConnectCallbacks.splice(index, 1)
      }
    }
  }

  onDisconnect(callback: () => void): () => void {
    this.onDisconnectCallbacks.push(callback)
    return () => {
      const index = this.onDisconnectCallbacks.indexOf(callback)
      if (index > -1) {
        this.onDisconnectCallbacks.splice(index, 1)
      }
    }
  }

  get isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }
}

// Singleton WebSocket instance
export const conversationWS = new ConversationWebSocket()
