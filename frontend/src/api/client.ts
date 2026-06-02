const API_BASE = '/api/v1'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status}: ${body}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// Projects
export const listProjects = () => request<any[]>('/projects')
export const getProject = (id: string) => request<any>(`/projects/${id}`)
export const createProject = (data: any) =>
  request<any>('/projects', { method: 'POST', body: JSON.stringify(data) })
export const deleteProject = (id: string) =>
  request<void>(`/projects/${id}`, { method: 'DELETE' })

// Pipeline
export const runPipeline = (projectId: string, data: any) =>
  request<any>(`/projects/${projectId}/pipeline`, { method: 'POST', body: JSON.stringify(data) })
export const runCodingTask = (projectId: string, data: any) =>
  request<any>(`/projects/${projectId}/code`, { method: 'POST', body: JSON.stringify(data) })

// Tasks
export const listTasks = (projectId: string) => request<any[]>(`/projects/${projectId}/tasks`)

// Memory
export const listMemory = (projectId: string) => request<any>(`/projects/${projectId}/memory`)
export const getMemoryContext = (projectId: string) =>
  request<any>(`/projects/${projectId}/memory/context`)

// Knowledge
export const searchKnowledge = (query: string) =>
  request<any[]>('/knowledge/search', { method: 'POST', body: JSON.stringify({ query }) })

// Skills
export const listSkills = () => request<any[]>('/skills')
export const seedSkills = () => request<any>('/skills/seed', { method: 'POST' })

// Runs
export const listRuns = (projectId: string) => request<any[]>(`/projects/${projectId}/runs`)

// Workspace
export const createWorkspace = (projectId: string) =>
  request<any>('/workspaces', { method: 'POST', body: JSON.stringify({ project_id: projectId }) })
export const execCommand = (wsId: string, command: string) =>
  request<any>(`/workspaces/${wsId}/exec`, { method: 'POST', body: JSON.stringify({ command }) })
export const listFiles = (wsId: string) => request<any>(`/workspaces/${wsId}/files`)
export const readFile = (wsId: string, path: string) =>
  request<any>(`/workspaces/${wsId}/files/read?path=${encodeURIComponent(path)}`)

// Metrics
export const getDashboard = (projectId?: string) =>
  request<any>(`/metrics/dashboard${projectId ? `?project_id=${projectId}` : ''}`)

// Deploy
export const deployProject = (projectId: string, data: any) =>
  request<any>(`/projects/${projectId}/deploy`, { method: 'POST', body: JSON.stringify(data) })

// Repair
export const triggerRepair = (projectId: string, taskId: string) =>
  request<any>(`/projects/${projectId}/repair?task_id=${taskId}`, { method: 'POST' })

// Health
export const healthCheck = () => fetch('/health').then(r => r.json())
