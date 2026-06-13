/**
 * AEP API client — Phase 5.
 *
 * Typed client for the AEP backend endpoints. Isolated from the main
 * app API client per the additive-only architectural rule.
 */

const API_BASE = import.meta.env.VITE_API_URL || '';
const AEP_PREFIX = `${API_BASE}/api/v1/aep`;

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem('auth_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const resp = await fetch(`${AEP_PREFIX}${path}`, {
    ...options,
    headers: { ...getAuthHeaders(), ...(options.headers || {}) },
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }
  return resp.json();
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface Repository {
  id: string;
  tenant_id: string;
  owner: string;
  name: string;
  provider: string;
  default_branch: string;
  auth_method: string;
  clone_url: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Execution {
  id: string;
  tenant_id: string;
  title: string;
  description: string | null;
  state: string;
  branch: string | null;
  token_input: number;
  token_output: number;
  error: string | null;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface FeatureFlag {
  name: string;
  enabled: boolean;
  default: boolean;
  phase: number;
  description: string;
}

export interface Plugin {
  name: string;
  feature_flag: string;
  model: string;
  fallback_model: string | null;
  description: string;
  active: boolean;
}

export interface TaskSubmission {
  title: string;
  description: string;
  repository_id?: string;
  branch?: string;
}

// ── Repositories ──────────────────────────────────────────────────────────

export async function listRepositories(): Promise<{ repositories: Repository[]; count: number }> {
  return request('/repositories');
}

export async function registerRepository(data: {
  owner: string;
  name: string;
  provider?: string;
  default_branch?: string;
  auth_method?: string;
}): Promise<Repository> {
  return request('/repositories', { method: 'POST', body: JSON.stringify(data) });
}

export async function deleteRepository(id: string): Promise<void> {
  await request(`/repositories/${id}`, { method: 'DELETE' });
}

// ── Executions ────────────────────────────────────────────────────────────

export async function listExecutions(): Promise<{ executions: Execution[]; count: number }> {
  return request('/executions');
}

export async function getExecution(id: string): Promise<Execution> {
  return request(`/executions/${id}`);
}

export async function submitTask(data: TaskSubmission): Promise<Execution> {
  return request('/executions', { method: 'POST', body: JSON.stringify(data) });
}

export async function triggerPlanning(id: string): Promise<Execution> {
  return request(`/executions/${id}/plan`, { method: 'POST' });
}

export async function approveExecution(id: string): Promise<Execution> {
  return request(`/executions/${id}/approve`, { method: 'POST' });
}

export async function rejectExecution(id: string, reason?: string): Promise<Execution> {
  return request(`/executions/${id}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason: reason || 'Plan rejected by operator' }),
  });
}

export async function runExecution(id: string): Promise<Execution> {
  return request(`/executions/${id}/execute`, { method: 'POST' });
}

// ── Feature Flags ─────────────────────────────────────────────────────────

export async function listFlags(): Promise<{ flags: FeatureFlag[] }> {
  return request('/flags');
}

export async function toggleFlag(name: string, enabled: boolean): Promise<FeatureFlag> {
  return request(`/flags/${name}`, {
    method: 'PUT',
    body: JSON.stringify({ enabled }),
  });
}

// ── Plugins ───────────────────────────────────────────────────────────────

export async function listPlugins(): Promise<{ plugins: Plugin[] }> {
  return request('/plugins');
}

// ── Status ────────────────────────────────────────────────────────────────

export async function getStatus(): Promise<Record<string, unknown>> {
  return request('/status');
}
