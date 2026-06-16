/**
 * LLM Provider API Client
 * 
 * Manage custom LLM endpoints (Ollama, OpenRouter, Azure, etc.)
 */

const API = `${import.meta.env.VITE_API_URL || ''}/api/v1`

export interface LLMProvider {
  id: string
  user_id: string
  name: string
  provider_type: string
  base_url: string
  api_key_masked: string
  headers: Record<string, string>
  default_model: string
  available_models: string[]
  supports_streaming: boolean
  supports_tools: boolean
  supports_vision: boolean
  context_size: number
  max_tokens: number
  cost_per_1k_input: number
  cost_per_1k_output: number
  priority: number
  is_active: boolean
  is_default: boolean
  health_status: 'healthy' | 'degraded' | 'error' | 'unknown'
  health_message: string
  latency_ms: number | null
  request_count: number
  last_used_at: string | null
  created_at: string
  updated_at: string
}

export interface CreateProviderRequest {
  name: string
  provider_type?: string
  base_url: string
  api_key?: string
  headers?: Record<string, string>
  default_model: string
  available_models?: string[]
  supports_streaming?: boolean
  supports_tools?: boolean
  supports_vision?: boolean
  context_size?: number
  max_tokens?: number
  cost_per_1k_input?: number
  cost_per_1k_output?: number
  priority?: number
  is_default?: boolean
}

export interface UpdateProviderRequest {
  name?: string
  base_url?: string
  api_key?: string
  headers?: Record<string, string>
  default_model?: string
  available_models?: string[]
  supports_streaming?: boolean
  supports_tools?: boolean
  supports_vision?: boolean
  context_size?: number
  max_tokens?: number
  cost_per_1k_input?: number
  cost_per_1k_output?: number
  priority?: number
  is_active?: boolean
  is_default?: boolean
}

export interface TestConnectionRequest {
  base_url: string
  api_key: string
  provider_type?: string
  model: string
}

export interface TestConnectionResponse {
  success: boolean
  latency_ms: number
  message: string
  models_available?: string[]
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

export async function listProviders(): Promise<LLMProvider[]> {
  const response = await fetchWithAuth(`${API}/llm-providers`)
  if (!response.ok) {
    throw new Error(`Failed to list providers: ${response.status}`)
  }
  return response.json()
}

export async function getProvider(id: string): Promise<LLMProvider> {
  const response = await fetchWithAuth(`${API}/llm-providers/${id}`)
  if (!response.ok) {
    throw new Error(`Failed to get provider: ${response.status}`)
  }
  return response.json()
}

export async function createProvider(req: CreateProviderRequest): Promise<LLMProvider> {
  const response = await fetchWithAuth(`${API}/llm-providers`, {
    method: 'POST',
    body: JSON.stringify(req),
  })
  if (!response.ok) {
    throw new Error(`Failed to create provider: ${response.status}`)
  }
  return response.json()
}

export async function updateProvider(id: string, req: UpdateProviderRequest): Promise<LLMProvider> {
  const response = await fetchWithAuth(`${API}/llm-providers/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(req),
  })
  if (!response.ok) {
    throw new Error(`Failed to update provider: ${response.status}`)
  }
  return response.json()
}

export async function deleteProvider(id: string): Promise<void> {
  const response = await fetchWithAuth(`${API}/llm-providers/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete provider: ${response.status}`)
  }
}

export async function testConnection(req: TestConnectionRequest): Promise<TestConnectionResponse> {
  const response = await fetchWithAuth(`${API}/llm-providers/test`, {
    method: 'POST',
    body: JSON.stringify(req),
  })
  if (!response.ok) {
    throw new Error(`Failed to test connection: ${response.status}`)
  }
  return response.json()
}

export async function testSavedProvider(id: string): Promise<TestConnectionResponse> {
  const response = await fetchWithAuth(`${API}/llm-providers/${id}/test`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error(`Failed to test provider: ${response.status}`)
  }
  return response.json()
}

export async function getAvailableModels(): Promise<{
  models: Array<{
    id: string
    provider_id: string
    provider_name: string
    model: string
    provider_type: string
    health_status: string
  }>
  default_provider: string | null
}> {
  const response = await fetchWithAuth(`${API}/llm-providers/models/available`)
  if (!response.ok) {
    throw new Error(`Failed to get models: ${response.status}`)
  }
  return response.json()
}

// Preset configurations for popular providers
export const PROVIDER_PRESETS: Record<string, Partial<CreateProviderRequest>> = {
  ollama: {
    provider_type: 'ollama',
    base_url: 'http://localhost:11434',
    default_model: 'qwen3-coder:480b',
    supports_streaming: true,
    supports_tools: true,
    context_size: 32768,
    cost_per_1k_input: 0,
    cost_per_1k_output: 0,
  },
  openrouter: {
    provider_type: 'openai-compatible',
    base_url: 'https://openrouter.ai/api/v1',
    default_model: 'anthropic/claude-3.5-sonnet',
    supports_streaming: true,
    supports_tools: true,
    supports_vision: true,
    context_size: 200000,
    cost_per_1k_input: 0.003,
    cost_per_1k_output: 0.015,
  },
  openai: {
    provider_type: 'openai-compatible',
    base_url: 'https://api.openai.com/v1',
    default_model: 'gpt-4o-mini',
    supports_streaming: true,
    supports_tools: true,
    supports_vision: true,
    context_size: 128000,
    cost_per_1k_input: 0.15,
    cost_per_1k_output: 0.60,
  },
  anthropic: {
    provider_type: 'anthropic',
    base_url: 'https://api.anthropic.com/v1',
    default_model: 'claude-3-5-sonnet-20241022',
    supports_streaming: true,
    supports_tools: true,
    supports_vision: true,
    context_size: 200000,
    cost_per_1k_input: 0.003,
    cost_per_1k_output: 0.015,
  },
  azure: {
    provider_type: 'azure',
    base_url: 'https://your-resource.openai.azure.com/openai/deployments/your-deployment',
    default_model: 'gpt-4',
    supports_streaming: true,
    supports_tools: true,
    context_size: 128000,
    cost_per_1k_input: 0.03,
    cost_per_1k_output: 0.06,
  },
  lmstudio: {
    provider_type: 'openai-compatible',
    base_url: 'http://localhost:1234/v1',
    default_model: 'local-model',
    supports_streaming: true,
    supports_tools: false,
    context_size: 8192,
    cost_per_1k_input: 0,
    cost_per_1k_output: 0,
  },
}
