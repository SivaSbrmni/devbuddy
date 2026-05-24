import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'
import {
  Plug, Plus, Trash2, RefreshCw, CheckCircle2, XCircle,
  ChevronDown, ChevronRight, AlertCircle, Loader2, Zap,
  Database, Cloud, Server, Globe,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface McpConnection {
  id: string
  name: string
  description: string
  conn_type: string
  url: string
  has_api_key: boolean
  config: Record<string, string>
  is_active: boolean
  last_tested_at: string | null
  last_test_ok: boolean | null
  last_test_msg: string | null
  created_at: string
}

const CONN_TYPES = [
  { id: 'loki',        label: 'Loki (Grafana)',      icon: Database, hint: 'Self-hosted log aggregation' },
  { id: 'datadog',     label: 'Datadog',             icon: Cloud,    hint: 'Cloud monitoring & logs' },
  { id: 'cloudwatch',  label: 'AWS CloudWatch',      icon: Cloud,    hint: 'AWS log streams' },
  { id: 'custom_http', label: 'Custom HTTP',         icon: Globe,    hint: 'Any HTTP log endpoint' },
  { id: 'custom_mcp',  label: 'Custom MCP Server',   icon: Server,   hint: 'Standard MCP protocol' },
]

const TYPE_ICON: Record<string, React.ElementType> = {
  loki: Database, datadog: Cloud, cloudwatch: Cloud, custom_http: Globe, custom_mcp: Server,
}

const TYPE_COLOR: Record<string, string> = {
  loki:        'bg-orange-500/20 text-orange-300 border-orange-500/30',
  datadog:     'bg-purple-500/20 text-purple-300 border-purple-500/30',
  cloudwatch:  'bg-amber-500/20 text-amber-300 border-amber-500/30',
  custom_http: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  custom_mcp:  'bg-teal-500/20 text-teal-300 border-teal-500/30',
}

const EMPTY_FORM = {
  name: '', description: '', conn_type: 'loki', url: '', api_key: '', config: '{}', is_active: true,
}

export function McpConnectionsPage() {
  const [conns, setConns] = useState<McpConnection[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [testing, setTesting] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.get<McpConnection[]>('/api/v1/mcp/connections')
      setConns(data)
    } catch { /* silent */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleCreate = async () => {
    if (!form.name || !form.url) { setFormError('Name and URL are required'); return }
    let parsedConfig: Record<string, string> = {}
    try { parsedConfig = JSON.parse(form.config || '{}') } catch { setFormError('Config must be valid JSON'); return }
    setSaving(true); setFormError('')
    try {
      await api.post('/api/v1/mcp/connections', {
        name: form.name, description: form.description,
        conn_type: form.conn_type, url: form.url,
        api_key: form.api_key, config: parsedConfig,
        is_active: form.is_active,
      })
      setShowForm(false); setForm({ ...EMPTY_FORM }); load()
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : 'Failed to create')
    } finally { setSaving(false) }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this connection?')) return
    try { await api.delete(`/api/v1/mcp/connections/${id}`); load() } catch { /* silent */ }
  }

  const handleToggle = async (conn: McpConnection) => {
    try {
      await api.patch(`/api/v1/mcp/connections/${conn.id}`, { is_active: !conn.is_active })
      load()
    } catch { /* silent */ }
  }

  const handleTest = async (id: string) => {
    setTesting(id)
    try {
      await api.post(`/api/v1/mcp/connections/${id}/test`, {})
      load()
    } catch { /* silent */ }
    finally { setTesting(null) }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-teal-500/20 flex items-center justify-center">
            <Plug className="w-5 h-5 text-teal-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground">MCP Connections</h1>
            <p className="text-sm text-muted-foreground">Connect external log sources &amp; tool servers to DevBuddy</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={load}>
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
          </Button>
          <Button onClick={() => { setShowForm(true); setFormError('') }} className="gap-2">
            <Plus className="w-4 h-4" /> Add Connection
          </Button>
        </div>
      </div>

      {/* How it works */}
      <div className="rounded-xl border border-teal-500/20 bg-teal-500/5 p-4">
        <div className="flex items-start gap-3">
          <Zap className="w-4 h-4 text-teal-400 mt-0.5 shrink-0" />
          <div className="text-sm text-teal-200/80 leading-relaxed">
            <span className="font-semibold text-teal-300">How it works:</span> When you describe a task, DevBuddy queries
            all active MCP connections for recent logs and errors. This context is injected into the agent's prompts,
            enabling it to <span className="text-teal-300">diagnose production issues</span>, trace errors to code, and suggest targeted fixes.
          </div>
        </div>
      </div>

      {/* Add form */}
      {showForm && (
        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <h2 className="text-sm font-bold text-foreground">New MCP Connection</h2>

          {/* Type selector */}
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-2">Source Type</label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {CONN_TYPES.map(t => {
                const Icon = t.icon
                return (
                  <button
                    key={t.id}
                    onClick={() => setForm(f => ({ ...f, conn_type: t.id }))}
                    className={cn(
                      'flex items-center gap-2 px-3 py-2.5 rounded-lg border text-left text-sm transition-colors',
                      form.conn_type === t.id
                        ? 'border-teal-500/50 bg-teal-500/10 text-teal-300'
                        : 'border-border bg-background text-muted-foreground hover:text-foreground'
                    )}
                  >
                    <Icon className="w-4 h-4 shrink-0" />
                    <div>
                      <div className="text-xs font-semibold">{t.label}</div>
                      <div className="text-[10px] opacity-60">{t.hint}</div>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Fields */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">Name *</label>
              <input
                type="text" value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="Production Loki"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                {form.conn_type === 'loki' ? 'Loki Base URL *' : 'Endpoint URL *'}
              </label>
              <input
                type="text" value={form.url}
                onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
                placeholder={form.conn_type === 'loki' ? 'http://loki:3100' : 'https://api.example.com/logs'}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">API Key / Token</label>
              <input
                type="password" value={form.api_key}
                onChange={e => setForm(f => ({ ...f, api_key: e.target.value }))}
                placeholder="Leave blank if not required"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">Description</label>
              <input
                type="text" value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                placeholder="e.g. Production cluster logs"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>

          {form.conn_type === 'loki' && (
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">Default LogQL Filter (optional)</label>
              <input
                type="text"
                value={form.config === '{}' ? '' : (() => { try { return JSON.parse(form.config).filter || '' } catch { return '' } })()}
                onChange={e => setForm(f => ({ ...f, config: JSON.stringify({ filter: e.target.value }) }))}
                placeholder='e.g. |= "ERROR" or leave blank for all logs'
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          )}

          {formError && (
            <div className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle className="w-4 h-4 shrink-0" /> {formError}
            </div>
          )}

          <div className="flex items-center gap-3 pt-1">
            <Button onClick={handleCreate} disabled={saving} className="gap-2">
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              Save Connection
            </Button>
            <Button variant="ghost" onClick={() => { setShowForm(false); setFormError('') }}>Cancel</Button>
          </div>
        </div>
      )}

      {/* Connection list */}
      <div className="rounded-xl border border-border overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-muted-foreground flex items-center justify-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading connections...
          </div>
        ) : conns.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <Plug className="w-10 h-10 text-muted-foreground/30 mx-auto" />
            <p className="text-muted-foreground">No MCP connections yet</p>
            <p className="text-sm text-muted-foreground/60">Add a log source to give DevBuddy visibility into your production environment</p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {conns.map(conn => {
              const Icon = TYPE_ICON[conn.conn_type] ?? Plug
              const isExpanded = expanded === conn.id
              return (
                <div key={conn.id}>
                  <div className="flex items-center gap-3 px-4 py-3 hover:bg-accent/30 transition-colors">
                    <div className="w-8 h-8 rounded-lg bg-secondary flex items-center justify-center shrink-0">
                      <Icon className="w-4 h-4 text-muted-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-foreground">{conn.name}</span>
                        <span className={cn('text-[10px] font-bold px-1.5 py-0.5 rounded border', TYPE_COLOR[conn.conn_type] ?? '')}>
                          {conn.conn_type}
                        </span>
                        {!conn.is_active && (
                          <Badge variant="secondary" className="text-[10px]">disabled</Badge>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground truncate">{conn.url}</div>
                    </div>
                    {/* Test status */}
                    {conn.last_tested_at && (
                      <div className="shrink-0">
                        {conn.last_test_ok
                          ? <CheckCircle2 className="w-4 h-4 text-green-400" />
                          : <XCircle className="w-4 h-4 text-red-400" />}
                      </div>
                    )}
                    {/* Actions */}
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => handleTest(conn.id)}
                        disabled={testing === conn.id}
                        className="px-2.5 py-1.5 text-xs rounded-lg border border-border hover:bg-accent transition-colors text-muted-foreground hover:text-foreground"
                      >
                        {testing === conn.id ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Test'}
                      </button>
                      <button
                        onClick={() => handleToggle(conn)}
                        className={cn(
                          'px-2.5 py-1.5 text-xs rounded-lg border transition-colors',
                          conn.is_active
                            ? 'border-border hover:bg-accent text-muted-foreground'
                            : 'border-teal-500/30 bg-teal-500/10 text-teal-400 hover:bg-teal-500/20'
                        )}
                      >
                        {conn.is_active ? 'Disable' : 'Enable'}
                      </button>
                      <button
                        onClick={() => setExpanded(isExpanded ? null : conn.id)}
                        className="p-1.5 rounded hover:bg-accent text-muted-foreground transition-colors"
                      >
                        {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                      </button>
                      <button
                        onClick={() => handleDelete(conn.id)}
                        className="p-1.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  {isExpanded && (
                    <div className="px-4 pb-4 pt-1 bg-secondary/10 border-t border-border text-xs space-y-1.5">
                      {conn.description && <p className="text-muted-foreground">{conn.description}</p>}
                      <p><span className="text-muted-foreground">URL:</span> <code className="text-foreground">{conn.url}</code></p>
                      <p><span className="text-muted-foreground">API Key:</span> {conn.has_api_key ? '••••••••' : 'Not set'}</p>
                      {conn.last_test_msg && (
                        <p className={cn('font-mono', conn.last_test_ok ? 'text-green-400' : 'text-red-400')}>
                          Last test: {conn.last_test_msg}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
