import { supabase } from './supabase'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export const DEV_TOKEN_KEY = 'devbuddy_dev_token'

async function getAuthHeaders(): Promise<Record<string, string>> {
  const devToken = localStorage.getItem(DEV_TOKEN_KEY)
  if (devToken) return { Authorization: `Bearer ${devToken}` }
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = await getAuthHeaders()
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...headers, ...(options.headers || {}) },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}

export async function getWsUrl(taskId: string): Promise<string> {
  const devToken = localStorage.getItem(DEV_TOKEN_KEY)
  const { data } = await supabase.auth.getSession()
  const token = devToken || data.session?.access_token || ''
  const base = API_BASE.replace('http://', 'ws://').replace('https://', 'wss://')
  return `${base}/api/v1/tasks/${taskId}/stream?token=${token}`
}
