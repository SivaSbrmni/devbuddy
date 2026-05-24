import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'
import {
  Github, Plus, Trash2, RefreshCw, CheckCircle2, XCircle,
  GitBranch, FolderOpen, Loader2, AlertCircle, ChevronDown, ChevronRight,
  Lock, Unlock, Copy, Check,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface GithubConnection {
  id: string
  name: string
  repo_url: string
  default_branch: string
  has_token: boolean
  is_active: boolean
  clone_status: string | null
  cloned_at: string | null
  last_synced_at: string | null
  created_at: string
}

const CLONE_BADGE: Record<string, { label: string; class: string }> = {
  pending:  { label: 'Pending',  class: 'bg-slate-500/20 text-slate-300 border-slate-500/30' },
  cloning:  { label: 'Cloning…', class: 'bg-blue-500/20 text-blue-300 border-blue-500/30' },
  ready:    { label: 'Ready',    class: 'bg-teal-500/20 text-teal-300 border-teal-500/30' },
  failed:   { label: 'Failed',   class: 'bg-red-500/20 text-red-300 border-red-500/30' },
}

const EMPTY_FORM = { name: '', repo_url: '', default_branch: 'main', github_token: '', is_active: true }

export function GithubConnectionsPage() {
  const [repos, setRepos] = useState<GithubConnection[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [syncing, setSyncing] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [showToken, setShowToken] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.get<GithubConnection[]>('/api/v1/github/connections')
      setRepos(data)
    } catch { /* silent */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  // Poll cloning repos
  useEffect(() => {
    const cloning = repos.some(r => r.clone_status === 'cloning' || r.clone_status === 'pending')
    if (!cloning) return
    const t = setInterval(load, 4000)
    return () => clearInterval(t)
  }, [repos, load])

  const handleCreate = async () => {
    if (!form.name || !form.repo_url) { setFormError('Name and Repo URL are required'); return }
    if (!form.repo_url.startsWith('https://github.com/')) {
      setFormError('Only HTTPS GitHub URLs are supported (https://github.com/org/repo)')
      return
    }
    setSaving(true); setFormError('')
    try {
      await api.post('/api/v1/github/connections', {
        name: form.name,
        repo_url: form.repo_url.replace(/\.git$/, ''),
        default_branch: form.default_branch,
        github_token: form.github_token,
        is_active: form.is_active,
      })
      setShowForm(false); setForm({ ...EMPTY_FORM }); load()
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : 'Failed to add repository')
    } finally { setSaving(false) }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Remove this repository connection?')) return
    try { await api.delete(`/api/v1/github/connections/${id}`); load() } catch { /* silent */ }
  }

  const handleSync = async (id: string) => {
    setSyncing(id)
    try { await api.post(`/api/v1/github/connections/${id}/clone`, {}); load() } catch { /* silent */ }
    finally { setSyncing(null) }
  }

  const copyUrl = (url: string) => {
    navigator.clipboard.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-slate-700 flex items-center justify-center">
            <Github className="w-5 h-5 text-slate-300" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground">GitHub Repositories</h1>
            <p className="text-sm text-muted-foreground">Connect repos so DevBuddy can read and understand your codebase</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={load}>
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
          </Button>
          <Button onClick={() => { setShowForm(true); setFormError('') }} className="gap-2">
            <Plus className="w-4 h-4" /> Add Repository
          </Button>
        </div>
      </div>

      {/* Info box */}
      <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-4 space-y-2">
        <div className="flex items-start gap-3">
          <GitBranch className="w-4 h-4 text-blue-400 mt-0.5 shrink-0" />
          <div className="text-sm text-blue-200/80 leading-relaxed">
            <span className="font-semibold text-blue-300">Codebase awareness:</span> DevBuddy clones connected repositories
            into a local workspace. When you describe a bug fix or feature, the agent reads your actual code structure,
            imports, and patterns to generate context-aware solutions.
          </div>
        </div>
        <div className="flex items-start gap-3 pl-7">
          <Lock className="w-3.5 h-3.5 text-blue-500 mt-0.5 shrink-0" />
          <p className="text-xs text-blue-400/70">
            GitHub tokens are stored server-side and never sent back to the UI. Use a fine-grained PAT with <code className="font-mono">contents:read</code> permission only.
          </p>
        </div>
      </div>

      {/* Add form */}
      {showForm && (
        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <h2 className="text-sm font-bold text-foreground">Add Repository</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">Display Name *</label>
              <input
                type="text" value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="my-service"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">Repository URL *</label>
              <input
                type="text" value={form.repo_url}
                onChange={e => setForm(f => ({ ...f, repo_url: e.target.value }))}
                placeholder="https://github.com/org/repo"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">Default Branch</label>
              <input
                type="text" value={form.default_branch}
                onChange={e => setForm(f => ({ ...f, default_branch: e.target.value }))}
                placeholder="main"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                GitHub Token (PAT)
                <button onClick={() => setShowToken(s => !s)} className="ml-2 text-muted-foreground hover:text-foreground">
                  {showToken ? <Unlock className="w-3 h-3 inline" /> : <Lock className="w-3 h-3 inline" />}
                </button>
              </label>
              <input
                type={showToken ? 'text' : 'password'}
                value={form.github_token}
                onChange={e => setForm(f => ({ ...f, github_token: e.target.value }))}
                placeholder="ghp_... (needed for private repos)"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>

          {formError && (
            <div className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle className="w-4 h-4 shrink-0" /> {formError}
            </div>
          )}

          <div className="flex items-center gap-3 pt-1">
            <Button onClick={handleCreate} disabled={saving} className="gap-2">
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              Add &amp; Clone
            </Button>
            <Button variant="ghost" onClick={() => { setShowForm(false); setFormError('') }}>Cancel</Button>
          </div>
        </div>
      )}

      {/* Repo list */}
      <div className="rounded-xl border border-border overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-muted-foreground flex items-center justify-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading repositories...
          </div>
        ) : repos.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <Github className="w-10 h-10 text-muted-foreground/30 mx-auto" />
            <p className="text-muted-foreground">No repositories connected</p>
            <p className="text-sm text-muted-foreground/60">Add a GitHub repo to give DevBuddy deep codebase understanding</p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {repos.map(repo => {
              const badge = CLONE_BADGE[repo.clone_status ?? 'pending'] ?? CLONE_BADGE.pending
              const isExpanded = expanded === repo.id
              return (
                <div key={repo.id}>
                  <div className="flex items-center gap-3 px-4 py-3 hover:bg-accent/30 transition-colors">
                    <div className="w-8 h-8 rounded-lg bg-slate-700 flex items-center justify-center shrink-0">
                      <Github className="w-4 h-4 text-slate-300" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-foreground">{repo.name}</span>
                        <span className={cn('text-[10px] font-bold px-1.5 py-0.5 rounded border', badge.class)}>
                          {badge.label}
                        </span>
                        {repo.clone_status === 'cloning' && (
                          <Loader2 className="w-3 h-3 text-blue-400 animate-spin" />
                        )}
                        {repo.clone_status === 'ready' && (
                          <CheckCircle2 className="w-3.5 h-3.5 text-teal-400" />
                        )}
                        {repo.clone_status === 'failed' && (
                          <XCircle className="w-3.5 h-3.5 text-red-400" />
                        )}
                      </div>
                      <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <code className="truncate">{repo.repo_url}</code>
                        <button onClick={() => copyUrl(repo.repo_url)} className="shrink-0 hover:text-foreground">
                          {copied ? <Check className="w-3 h-3 text-teal-400" /> : <Copy className="w-3 h-3" />}
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => handleSync(repo.id)}
                        disabled={syncing === repo.id || repo.clone_status === 'cloning'}
                        title="Re-sync / pull latest"
                        className="px-2.5 py-1.5 text-xs rounded-lg border border-border hover:bg-accent transition-colors text-muted-foreground hover:text-foreground disabled:opacity-50"
                      >
                        {syncing === repo.id
                          ? <Loader2 className="w-3 h-3 animate-spin" />
                          : <RefreshCw className="w-3 h-3" />}
                      </button>
                      <button
                        onClick={() => setExpanded(isExpanded ? null : repo.id)}
                        className="p-1.5 rounded hover:bg-accent text-muted-foreground transition-colors"
                      >
                        {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                      </button>
                      <button
                        onClick={() => handleDelete(repo.id)}
                        className="p-1.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  {isExpanded && (
                    <div className="px-4 pb-4 pt-2 bg-secondary/10 border-t border-border text-xs space-y-1.5">
                      <div className="flex items-center gap-2">
                        <GitBranch className="w-3.5 h-3.5 text-muted-foreground" />
                        <span className="text-muted-foreground">Branch:</span>
                        <code className="text-foreground">{repo.default_branch}</code>
                      </div>
                      <div className="flex items-center gap-2">
                        <Lock className="w-3.5 h-3.5 text-muted-foreground" />
                        <span className="text-muted-foreground">Token:</span>
                        <span className={repo.has_token ? 'text-teal-400' : 'text-amber-400'}>
                          {repo.has_token ? '✓ Set' : 'Not set (public repos only)'}
                        </span>
                      </div>
                      {repo.cloned_at && (
                        <div className="flex items-center gap-2">
                          <FolderOpen className="w-3.5 h-3.5 text-muted-foreground" />
                          <span className="text-muted-foreground">Cloned:</span>
                          <span className="text-foreground">{new Date(repo.cloned_at).toLocaleString()}</span>
                        </div>
                      )}
                      {repo.last_synced_at && (
                        <div className="flex items-center gap-2">
                          <RefreshCw className="w-3.5 h-3.5 text-muted-foreground" />
                          <span className="text-muted-foreground">Last synced:</span>
                          <span className="text-foreground">{new Date(repo.last_synced_at).toLocaleString()}</span>
                        </div>
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
