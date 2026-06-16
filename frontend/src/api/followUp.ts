/**
 * Follow-up API Client
 * 
 * Detect and handle follow-up messages for task continuity.
 */

const API = `${import.meta.env.VITE_API_URL || ''}/api/v1`

export interface FollowUpAnalysis {
  is_follow_up: boolean
  confidence: number
  previous_task_id: string | null
  suggested_action: 'continue' | 'new_branch' | 'new_task'
  previous_branch: string | null
  inherited_files: string[]
}

export interface CreateTaskWithContext {
  task_id: string
  is_follow_up: boolean
  parent_task_id: string | null
  branch: string
  previous_branch: string | null
  inherited_files: string[]
  confidence: number
  suggested_prompt_context: string
}

export interface TaskChainItem {
  id: string
  title: string
  branch: string
  status: string
  commit_hash: string | null
  pr_url: string | null
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

export async function analyzeMessage(
  conversationId: string,
  message: string
): Promise<FollowUpAnalysis> {
  const response = await fetchWithAuth(`${API}/follow-up/analyze`, {
    method: 'POST',
    body: JSON.stringify({ conversation_id: conversationId, message }),
  })
  if (!response.ok) {
    throw new Error(`Failed to analyze message: ${response.status}`)
  }
  return response.json()
}

export async function createTaskWithContext(
  conversationId: string,
  message: string,
  forceNewTask: boolean = false
): Promise<CreateTaskWithContext> {
  const response = await fetchWithAuth(`${API}/follow-up/create-task`, {
    method: 'POST',
    body: JSON.stringify({ 
      conversation_id: conversationId, 
      message,
      force_new_task: forceNewTask,
    }),
  })
  if (!response.ok) {
    throw new Error(`Failed to create task: ${response.status}`)
  }
  return response.json()
}

export async function continueOnBranch(
  conversationId: string,
  message: string
): Promise<CreateTaskWithContext> {
  const response = await fetchWithAuth(`${API}/follow-up/continue-on-branch`, {
    method: 'POST',
    body: JSON.stringify({ 
      conversation_id: conversationId, 
      message,
    }),
  })
  if (!response.ok) {
    throw new Error(`Failed to continue on branch: ${response.status}`)
  }
  return response.json()
}

export async function getTaskChain(taskId: string): Promise<{ chain: TaskChainItem[] }> {
  const response = await fetchWithAuth(`${API}/follow-up/task-chain/${taskId}`)
  if (!response.ok) {
    throw new Error(`Failed to get task chain: ${response.status}`)
  }
  return response.json()
}
