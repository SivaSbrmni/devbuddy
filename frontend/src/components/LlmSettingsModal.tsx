import { useState, useEffect, useCallback } from 'react'
import { Settings, X, CheckCircle2, Loader2, Eye, EyeOff, RefreshCw, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import { DEV_TOKEN_KEY } from '@/lib/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const PROVIDERS = [
  { id: 'ollama',   label: 'Ollama (local)',   hint: 'No API key needed' },
  { id: 'groq',     label: 'Groq',             hint: 'Free tier • Fast llama3' },
  { id: 'together', label: 'Together AI',      hint: 'Meta llama models' },
  { id: 'openai',   label: 'OpenAI',           hint: 'GPT-4o / GPT-4o-mini' },
  { id: 'custom',   label: 'Custom (OpenAI-compat)', hint: 'Set your own base URL' },
]

interface LlmConfig {
  provider: string
  model: string
  has_api_key: boolean
  api_base: string | null
  ollama_url: string
}

interface LlmSettingsModalProps {
  open: boolean
  onClose: () => void
  onSaved: (provider: string, model: string) => void
}

export function LlmSettingsModal({ open, onClose, onSaved }: LlmSettingsModalProps) {
  const [config, setConfig]     = useState<LlmConfig | null>(null)
  const [provider, setProvider] = useState('ollama')
  const [model, setModel]       = useState('')
  const [apiKey, setApiKey]     = useState('')
  const [apiBase, setApiBase]   = useState('')
  const [showKey, setShowKey]   = useState(false)
  const [models, setModels]     = useState<string[]>([])
  const [loadingModels, setLoadingModels] = useState(false)
  const [saving, setSaving]     = useState(false)
  const [saved, setSaved]       = useState(false)
  const [error, setError]       = useState('')
  const [modelOpen, setModelOpen] = useState(false)

  const authHeaders = useCallback((): Record<string, string> => {
    const token = localStorage.getItem(DEV_TOKEN_KEY)
    return token ? { 'X-Auth-Token': token } : {}
  }, [])

  const loadConfig = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/api/v1/llm/config`, { headers: authHeaders() })
      if (r.ok) {
        const data: LlmConfig = await r.json()
        setConfig(data)
        setProvider(data.provider)
        setModel(data.model)
        setApiBase(data.api_base ?? '')
      }
    } catch { /* silent */ }
  }, [authHeaders])

  const fetchModels = useCallback(async (prov: string, key?: string) => {
    setLoadingModels(true)
    setModels([])
    try {
      const params = new URLSearchParams({ provider: prov })
      if (key) params.set('api_key', key)
      const r = await fetch(`${API_BASE}/api/v1/llm/models?${params}`, { headers: authHeaders() })
      if (r.ok) {
        const data = await r.json()
        setModels(data.models ?? [])
        if (data.models?.length && !data.models.includes(model)) {
          setModel(data.models[0])
        }
      }
    } catch { /* silent */ }
    finally { setLoadingModels(false) }
  }, [authHeaders, model])

  useEffect(() => {
    if (open) { loadConfig(); setSaved(false); setError('') }
  }, [open, loadConfig])

  useEffect(() => {
    if (open && provider) fetchModels(provider, apiKey || undefined)
  }, [provider, open])  // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = async () => {
    if (!model) { setError('Select a model first'); return }
    setSaving(true); setError('')
    try {
      const body: Record<string, string> = { provider, model }
      if (apiKey) body.api_key = apiKey
      if (apiBase) body.api_base = apiBase
      const r = await fetch(`${API_BASE}/api/v1/llm/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(body),
      })
      if (!r.ok) { setError(`Save failed: ${r.status}`); return }
      setSaved(true)
      onSaved(provider, model)
      setTimeout(onClose, 800)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  if (!open) return null

  const needsKey = provider !== 'ollama'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-md mx-4 rounded-2xl border border-white/10 bg-[#0b1628] shadow-2xl shadow-black/60">
        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-white/8">
          <Settings className="w-4 h-4 text-teal-400" />
          <h2 className="text-sm font-bold text-white flex-1">LLM Provider Settings</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          {/* Provider selector */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-widest text-slate-500 mb-2">Provider</label>
            <div className="space-y-1.5">
              {PROVIDERS.map(p => (
                <button
                  key={p.id}
                  onClick={() => { setProvider(p.id); setModel('') }}
                  className={cn(
                    'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg border text-left transition-colors',
                    provider === p.id
                      ? 'border-teal-500/50 bg-teal-500/10 text-white'
                      : 'border-white/8 bg-white/3 text-slate-400 hover:bg-white/6 hover:text-slate-200'
                  )}
                >
                  <span className={cn(
                    'w-3 h-3 rounded-full border-2 shrink-0',
                    provider === p.id ? 'border-teal-400 bg-teal-400' : 'border-slate-600'
                  )} />
                  <span className="text-xs font-semibold flex-1">{p.label}</span>
                  <span className="text-[10px] text-slate-500">{p.hint}</span>
                </button>
              ))}
            </div>
          </div>

          {/* API Key — shown for cloud providers */}
          {needsKey && (
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-widest text-slate-500 mb-2">
                API Key {config?.has_api_key && <span className="text-teal-400 ml-1">✓ saved</span>}
              </label>
              <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                <input
                  type={showKey ? 'text' : 'password'}
                  placeholder={config?.has_api_key ? '••••••••••••••••••••••• (leave blank to keep)' : `Paste your ${provider} API key...`}
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                  className="flex-1 bg-transparent text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none font-mono"
                />
                <button onClick={() => setShowKey(s => !s)} className="text-slate-500 hover:text-slate-300">
                  {showKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>
          )}

          {/* Custom base URL */}
          {provider === 'custom' && (
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-widest text-slate-500 mb-2">API Base URL</label>
              <input
                type="text"
                placeholder="https://your-endpoint.com/v1"
                value={apiBase}
                onChange={e => setApiBase(e.target.value)}
                className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none font-mono"
              />
            </div>
          )}

          {/* Model picker */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-[11px] font-bold uppercase tracking-widest text-slate-500">Model</label>
              <button
                onClick={() => fetchModels(provider, apiKey || undefined)}
                className="flex items-center gap-1 text-[10px] text-teal-400 hover:text-teal-300"
              >
                <RefreshCw className={cn('w-2.5 h-2.5', loadingModels && 'animate-spin')} />
                {loadingModels ? 'Loading...' : 'Refresh'}
              </button>
            </div>

            {/* Custom text input */}
            <div className="relative">
              <button
                onClick={() => setModelOpen(o => !o)}
                className="w-full flex items-center gap-2 rounded-lg border border-white/10 bg-black/20 px-3 py-2.5 text-left transition-colors hover:border-white/20"
              >
                <span className={cn('flex-1 text-xs font-mono', model ? 'text-slate-200' : 'text-slate-600')}>
                  {model || 'Select or type a model...'}
                </span>
                {loadingModels
                  ? <Loader2 className="w-3.5 h-3.5 text-slate-500 animate-spin shrink-0" />
                  : <ChevronDown className="w-3.5 h-3.5 text-slate-500 shrink-0" />}
              </button>

              {modelOpen && (
                <div className="absolute z-20 top-full mt-1 w-full rounded-lg border border-white/10 bg-[#0d1e35] shadow-xl max-h-52 overflow-y-auto">
                  {/* Custom entry */}
                  <div className="px-3 py-2 border-b border-white/8">
                    <input
                      autoFocus
                      type="text"
                      placeholder="Type custom model ID..."
                      value={model}
                      onChange={e => setModel(e.target.value)}
                      className="w-full bg-transparent text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none font-mono"
                    />
                  </div>
                  {models.length === 0 && !loadingModels && (
                    <div className="px-3 py-3 text-[11px] text-slate-500">
                      {needsKey && !apiKey ? 'Enter API key above then click Refresh' : 'No models found'}
                    </div>
                  )}
                  {models.map(m => (
                    <button
                      key={m}
                      onClick={() => { setModel(m); setModelOpen(false) }}
                      className={cn(
                        'w-full px-3 py-2 text-left text-xs font-mono hover:bg-white/6 transition-colors',
                        model === m ? 'text-teal-300 bg-teal-500/10' : 'text-slate-300'
                      )}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Error */}
          {error && <p className="text-xs text-red-400">{error}</p>}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-3 px-5 py-4 border-t border-white/8">
          <button onClick={onClose} className="flex-1 py-2 rounded-lg border border-white/10 text-xs text-slate-400 hover:text-slate-200 transition-colors">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !model}
            className={cn(
              'flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition-colors',
              saved
                ? 'bg-teal-500/30 border border-teal-500/50 text-teal-300'
                : 'bg-teal-600 hover:bg-teal-500 text-white disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            {saved && <CheckCircle2 className="w-3.5 h-3.5" />}
            {saved ? 'Saved!' : saving ? 'Saving...' : 'Save & Apply'}
          </button>
        </div>
      </div>
    </div>
  )
}
