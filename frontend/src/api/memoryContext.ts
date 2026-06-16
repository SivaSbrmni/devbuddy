/**
 * Memory Context API Client
 * 
 * Fetch and manage conversation/user/repository memory.
 */

const API = `${import.meta.env.VITE_API_URL || ''}/api/v1`

export interface MemoryContext {
  conversation_id: string | null
  user_preferences: {
    preferred_language?: string
    preferred_framework?: string
    coding_style?: string
    commit_style?: string
    pr_style?: string
    testing_preference?: string
    documentation_style?: string
    response_style?: string
    preferred_architecture?: string
    custom_instructions?: string
  }
  repository_memory: {
    architecture?: Record<string, any>
    coding_standards?: string
    recent_changes?: Array<{
      task_id: string
      title: string
      files: string[]
      timestamp: string
    }>
    known_issues?: Array<{
      title: string
      status: string
      workarounds?: string[]
    }>
  }
  conversation_memory: {
    summary: string
    current_goal: string
    completed_tasks: Array<{
      task_id: string
      title: string
      summary: string
      branch: string
      commit_hash?: string
      pr_url?: string
      modified_files: string[]
      completed_at: string
    }>
    open_tasks: Array<{
      title: string
      description: string
      status: string
      created_at: string
    }>
    modified_files: string[]
    important_decisions: Array<{
      content: string
      context?: Record<string, any>
      timestamp: string
    }>
  }
  previous_task: {
    summary: string
    branch: string
    commit: string
    pr_url?: string
    files: string[]
  } | null
}

export interface UserPreferences {
  preferred_language?: string
  preferred_framework?: string
  coding_style?: string
  commit_style?: string
  pr_style?: string
  testing_preference?: string
  documentation_style?: string
  response_style?: string
  preferred_architecture?: string
  custom_instructions?: string
}

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

export async function getConversationMemory(conversationId: string): Promise<MemoryContext> {
  const response = await fetchWithAuth(`${API}/memory-context/conversation/${conversationId}`)
  if (!response.ok) {
    throw new Error(`Failed to get memory context: ${response.status}`)
  }
  return response.json()
}

export async function updateConversationGoal(
  conversationId: string,
  goal: string
): Promise<{ success: boolean; goal: string }> {
  const response = await fetchWithAuth(`${API}/memory-context/conversation/${conversationId}/goal`, {
    method: 'POST',
    body: JSON.stringify({ goal }),
  })
  if (!response.ok) {
    throw new Error(`Failed to update goal: ${response.status}`)
  }
  return response.json()
}

export async function recordDecision(
  conversationId: string,
  decision: string,
  context?: Record<string, any>
): Promise<{ success: boolean; decision: string }> {
  const response = await fetchWithAuth(`${API}/memory-context/conversation/${conversationId}/decision`, {
    method: 'POST',
    body: JSON.stringify({ decision, context }),
  })
  if (!response.ok) {
    throw new Error(`Failed to record decision: ${response.status}`)
  }
  return response.json()
}

export async function addOpenTask(
  conversationId: string,
  title: string,
  description: string = ''
): Promise<{ success: boolean; title: string }> {
  const response = await fetchWithAuth(`${API}/memory-context/conversation/${conversationId}/open-task`, {
    method: 'POST',
    body: JSON.stringify({ title, description }),
  })
  if (!response.ok) {
    throw new Error(`Failed to add open task: ${response.status}`)
  }
  return response.json()
}

export async function getUserPreferences(): Promise<UserPreferences> {
  const response = await fetchWithAuth(`${API}/memory-context/user/preferences`)
  if (!response.ok) {
    throw new Error(`Failed to get user preferences: ${response.status}`)
  }
  return response.json()
}

export async function updateUserPreferences(updates: Partial<UserPreferences>): Promise<{ success: boolean }> {
  const response = await fetchWithAuth(`${API}/memory-context/user/preferences`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  })
  if (!response.ok) {
    throw new Error(`Failed to update preferences: ${response.status}`)
  }
  return response.json()
}
