import { useState, useEffect, useRef } from 'react'
import Icon from './Icon'
import { useGitHub, Repo } from '../context/GitHubContext'

const BACKEND = import.meta.env.VITE_API_URL || ''
const API = `${BACKEND}/api/v1`

interface Props {
  token: string
  isOpen: boolean
  onClose: () => void
  onSelectRepo: (repo: Repo) => void
}

type View = 'selector' | 'create' | 'dashboard'

const LANG_COLORS: Record<string, string> = {
  TypeScript: '#3178c6', JavaScript: '#f7df1e', Python: '#3572A5',
  Go: '#00ADD8', Rust: '#dea584', Java: '#b07219', 'C++': '#f34b7d',
  Ruby: '#701516', Swift: '#F05138', Kotlin: '#A97BFF', default: '#6e7681',
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 2) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  if (d < 30) return `${d}d ago`
  return new Date(dateStr).toLocaleDateString()
}

export default function GitHubPanel({ token, isOpen, onClose, onSelectRepo }: Props) {
  const { connected, githubLogin, loading, connect, repos, reposLoading, fetchRepos, searchRepos, activeRepo, setActiveRepo } = useGitHub()
  const [view, setView] = useState<View>('selector')
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState<Repo[] | null>(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [filterPrivate, setFilterPrivate] = useState<'all' | 'public' | 'private'>('all')
  const [sortBy, setSortBy] = useState<'pushed' | 'stars' | 'name'>('pushed')
  const [dashRepo, setDashRepo] = useState<Repo | null>(null)
  const [branches, setBranches] = useState<any[]>([])
  const [issues, setIssues] = useState<any[]>([])
  const [prs, setPrs] = useState<any[]>([])
  const [languages, setLanguages] = useState<Record<string, number>>({})
  const [dashLoading, setDashLoading] = useState(false)
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Create repo state
  const [createName, setCreateName] = useState('')
  const [createDesc, setCreateDesc] = useState('')
  const [createPrivate, setCreatePrivate] = useState(true)
  const [createInit, setCreateInit] = useState(true)
  const [createTemplate, setCreateTemplate] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')

  useEffect(() => {
    if (!isOpen) return
    if (activeRepo) { openDashboard(activeRepo); return }
    setView('selector')
  }, [isOpen])

  useEffect(() => {
    if (!search.trim()) { setSearchResults(null); return }
    if (searchTimer.current) clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(async () => {
      setSearchLoading(true)
      const r = await searchRepos(search)
      setSearchResults(r)
      setSearchLoading(false)
    }, 350)
  }, [search])

  const openDashboard = async (repo: Repo) => {
    setDashRepo(repo)
    setView('dashboard')
    setDashLoading(true)
    try {
      const [b, i, p, l] = await Promise.all([
        fetch(`${API}/github/repos/${repo.owner}/${repo.name}/branches?token=${encodeURIComponent(token)}`).then(r => r.ok ? r.json() : []),
        fetch(`${API}/github/repos/${repo.owner}/${repo.name}/issues?token=${encodeURIComponent(token)}`).then(r => r.ok ? r.json() : []),
        fetch(`${API}/github/repos/${repo.owner}/${repo.name}/pulls?token=${encodeURIComponent(token)}`).then(r => r.ok ? r.json() : []),
        fetch(`${API}/github/repos/${repo.owner}/${repo.name}/languages?token=${encodeURIComponent(token)}`).then(r => r.ok ? r.json() : {}),
      ])
      setBranches(b); setIssues(i); setPrs(p); setLanguages(l)
    } finally {
      setDashLoading(false)
    }
  }

  const handleSelectRepo = (repo: Repo) => {
    setActiveRepo(repo)
    onSelectRepo(repo)
    onClose()
  }

  const handleCreateRepo = async () => {
    if (!createName.trim()) { setCreateError('Repository name is required'); return }
    setCreating(true); setCreateError('')
    try {
      const resp = await fetch(`${API}/github/repos?token=${encodeURIComponent(token)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: createName.trim(), description: createDesc, private: createPrivate, auto_init: createInit, gitignore_template: createTemplate }),
      })
      if (!resp.ok) { const e = await resp.text(); setCreateError(e); return }
      const repo = await resp.json()
      await fetchRepos()
      openDashboard(repo)
    } catch (e: any) {
      setCreateError(e.message)
    } finally {
      setCreating(false)
    }
  }

  const displayRepos = searchResults ?? repos
  const filteredRepos = displayRepos
    .filter(r => filterPrivate === 'all' ? true : filterPrivate === 'private' ? r.private : !r.private)
    .sort((a, b) => {
      if (sortBy === 'stars') return b.stargazers_count - a.stargazers_count
      if (sortBy === 'name') return a.name.localeCompare(b.name)
      return new Date(b.pushed_at).getTime() - new Date(a.pushed_at).getTime()
    })

  const totalLangBytes = Object.values(languages).reduce((s, v) => s + v, 0)

  if (!isOpen) return null

  return (
    <div
      onClick={onClose}
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)', zIndex: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, animation: 'fadeIn 0.15s ease' }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{ width: '100%', maxWidth: 720, maxHeight: '90vh', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius-xl)', boxShadow: '0 32px 80px rgba(0,0,0,0.6)', display: 'flex', flexDirection: 'column', overflow: 'hidden', animation: 'modalContent 0.2s ease' }}
      >
        {/* Header */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: 'linear-gradient(135deg, #24292e, #444d56)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Icon name="git" size={18} style={{ color: 'white' }} />
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)' }}>GitHub</div>
              {connected && githubLogin && <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>@{githubLogin}</div>}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {connected && view === 'selector' && (
              <button onClick={() => setView('create')} style={{ fontSize: 12, color: 'var(--accent-hover)', background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.25)', borderRadius: 'var(--radius-md)', padding: '5px 12px', cursor: 'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 5 }}>
                <Icon name="plus" size={12} /> New repo
              </button>
            )}
            {connected && (
              <button
                onClick={connect}
                title="Re-authorize to grant workflow permissions"
                style={{ fontSize: 12, color: 'var(--text-muted)', background: 'transparent', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '5px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5 }}
              >
                <Icon name="refresh" size={12} /> Reconnect
              </button>
            )}
            {view !== 'selector' && (
              <button onClick={() => setView('selector')} style={{ fontSize: 12, color: 'var(--text-muted)', background: 'transparent', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '5px 10px', cursor: 'pointer' }}>
                ← Back
              </button>
            )}
            <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-faint)', cursor: 'pointer', padding: '4px 6px', borderRadius: 'var(--radius-sm)', display: 'flex' }} onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = 'var(--text)'; (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.06)' }} onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = 'var(--text-faint)'; (e.currentTarget as HTMLElement).style.background = 'none' }}>
              <Icon name="close" size={16} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>

          {/* ── Not connected ── */}
          {!loading && !connected && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '60px 40px', gap: 24, textAlign: 'center' }}>
              <div style={{ width: 64, height: 64, borderRadius: 16, background: 'linear-gradient(135deg, #24292e, #444d56)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 8px 24px rgba(0,0,0,0.4)' }}>
                <Icon name="git" size={32} style={{ color: 'white' }} />
              </div>
              <div>
                <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)', marginBottom: 8 }}>Connect GitHub</div>
                <div style={{ fontSize: 14, color: 'var(--text-dim)', lineHeight: 1.6, maxWidth: 360 }}>
                  Let DevBuddy work directly inside your repositories. Read code, create branches, open pull requests — automatically.
                </div>
              </div>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
                {['Read repos', 'Create branches', 'Open PRs', 'Manage issues'].map(f => (
                  <div key={f} style={{ fontSize: 12, color: 'var(--text-faint)', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-subtle)', borderRadius: 20, padding: '4px 12px' }}>{f}</div>
                ))}
              </div>
              <button
                onClick={connect}
                style={{ background: '#24292e', color: 'white', border: 'none', borderRadius: 'var(--radius-md)', padding: '12px 28px', fontSize: 14, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10, boxShadow: '0 4px 16px rgba(0,0,0,0.4)', transition: 'all 0.15s ease' }}
                onMouseEnter={e => (e.currentTarget.style.background = '#444d56')}
                onMouseLeave={e => (e.currentTarget.style.background = '#24292e')}
              >
                <Icon name="git" size={18} /> Continue with GitHub
              </button>
            </div>
          )}

          {/* ── Loading ── */}
          {loading && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 60, gap: 12, color: 'var(--text-faint)', fontSize: 13 }}>
              <Icon name="loader" size={16} /> Checking GitHub connection...
            </div>
          )}

          {/* ── Repo Selector ── */}
          {!loading && connected && view === 'selector' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              {/* Search + filter bar */}
              <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: 180, position: 'relative' }}>
                  <Icon name="command" size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-faint)' }} />
                  <input
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    placeholder="Search repositories..."
                    style={{ width: '100%', paddingLeft: 32, paddingRight: 12, paddingTop: 7, paddingBottom: 7, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', color: 'var(--text)', fontSize: 13, outline: 'none', boxSizing: 'border-box' }}
                  />
                </div>
                <select value={filterPrivate} onChange={e => setFilterPrivate(e.target.value as any)} style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', color: 'var(--text)', fontSize: 12, padding: '6px 8px', cursor: 'pointer' }}>
                  <option value="all">All</option>
                  <option value="public">Public</option>
                  <option value="private">Private</option>
                </select>
                <select value={sortBy} onChange={e => setSortBy(e.target.value as any)} style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', color: 'var(--text)', fontSize: 12, padding: '6px 8px', cursor: 'pointer' }}>
                  <option value="pushed">Recent</option>
                  <option value="stars">Stars</option>
                  <option value="name">Name</option>
                </select>
                <button onClick={fetchRepos} title="Refresh" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', color: 'var(--text-muted)', padding: '6px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
                  <Icon name="loader" size={13} />
                </button>
              </div>

              {/* Repo list */}
              {(reposLoading || searchLoading) ? (
                <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-faint)', fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                  <Icon name="loader" size={14} /> Loading repositories...
                </div>
              ) : filteredRepos.length === 0 ? (
                <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-faint)', fontSize: 13 }}>
                  {search ? 'No repositories found' : 'No repositories yet'}
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  {filteredRepos.map(repo => (
                    <RepoCard key={repo.id} repo={repo} onOpen={() => openDashboard(repo)} onSelect={() => handleSelectRepo(repo)} isActive={activeRepo?.id === repo.id} />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Create Repo ── */}
          {connected && view === 'create' && (
            <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 20 }}>
              <div>
                <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)', marginBottom: 6 }}>Create a new repository</div>
                <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>DevBuddy will initialize it and start working immediately.</div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <Field label="Repository name *">
                  <input value={createName} onChange={e => setCreateName(e.target.value)} placeholder="my-awesome-project" style={inputStyle} />
                </Field>
                <Field label="Description">
                  <input value={createDesc} onChange={e => setCreateDesc(e.target.value)} placeholder="What does this project do?" style={inputStyle} />
                </Field>
                <Field label=".gitignore template">
                  <select value={createTemplate} onChange={e => setCreateTemplate(e.target.value)} style={{ ...inputStyle, cursor: 'pointer' }}>
                    <option value="">None</option>
                    <option value="Node">Node</option>
                    <option value="Python">Python</option>
                    <option value="Go">Go</option>
                    <option value="Rust">Rust</option>
                    <option value="Java">Java</option>
                  </select>
                </Field>
                <div style={{ display: 'flex', gap: 16 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, color: 'var(--text-muted)' }}>
                    <input type="checkbox" checked={createPrivate} onChange={e => setCreatePrivate(e.target.checked)} /> Private
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, color: 'var(--text-muted)' }}>
                    <input type="checkbox" checked={createInit} onChange={e => setCreateInit(e.target.checked)} /> Initialize with README
                  </label>
                </div>
                {createError && <div style={{ fontSize: 12, color: 'var(--error)', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--radius-md)', padding: '8px 12px' }}>{createError}</div>}
                <button
                  onClick={handleCreateRepo}
                  disabled={creating || !createName.trim()}
                  style={{ background: creating || !createName.trim() ? 'var(--border)' : 'linear-gradient(135deg, var(--accent), var(--accent-hover))', color: creating || !createName.trim() ? 'var(--text-faint)' : 'white', border: 'none', borderRadius: 'var(--radius-md)', padding: '11px 24px', fontSize: 13, fontWeight: 600, cursor: creating || !createName.trim() ? 'not-allowed' : 'pointer', marginTop: 4, display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center' }}
                >
                  {creating ? <><Icon name="loader" size={14} /> Creating...</> : <><Icon name="plus" size={14} /> Create Repository</>}
                </button>
              </div>
            </div>
          )}

          {/* ── Repository Dashboard ── */}
          {connected && view === 'dashboard' && dashRepo && (
            <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 20 }}>
              {/* Repo header */}
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                    <img src={dashRepo.owner_avatar} alt="" style={{ width: 20, height: 20, borderRadius: '50%' }} />
                    <span style={{ fontSize: 13, color: 'var(--text-faint)' }}>{dashRepo.owner} /</span>
                    <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)' }}>{dashRepo.name}</span>
                    <span style={{ fontSize: 10, color: dashRepo.private ? 'var(--text-faint)' : 'var(--success)', background: dashRepo.private ? 'rgba(255,255,255,0.06)' : 'rgba(16,185,129,0.1)', border: `1px solid ${dashRepo.private ? 'var(--border)' : 'rgba(16,185,129,0.2)'}`, borderRadius: 10, padding: '1px 7px', fontWeight: 600 }}>
                      {dashRepo.private ? 'Private' : 'Public'}
                    </span>
                  </div>
                  {dashRepo.description && <div style={{ fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.5 }}>{dashRepo.description}</div>}
                </div>
                <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                  <a href={dashRepo.html_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 11, color: 'var(--text-muted)', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '4px 10px', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Icon name="folder" size={11} /> GitHub ↗
                  </a>
                  <button
                    onClick={() => handleSelectRepo(dashRepo)}
                    style={{ fontSize: 12, color: 'white', background: 'linear-gradient(135deg, var(--accent), var(--accent-hover))', border: 'none', borderRadius: 'var(--radius-md)', padding: '5px 14px', cursor: 'pointer', fontWeight: 600 }}
                  >
                    Work here →
                  </button>
                </div>
              </div>

              {/* Stats row */}
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                {[
                  { icon: 'git', label: 'Branch', value: dashRepo.default_branch },
                  { icon: 'zap', label: 'Stars', value: dashRepo.stargazers_count.toLocaleString() },
                  { icon: 'folder', label: 'Forks', value: dashRepo.forks_count.toLocaleString() },
                  { icon: 'info', label: 'Issues', value: dashRepo.open_issues_count.toLocaleString() },
                  { icon: 'file', label: 'Size', value: dashRepo.size > 1024 ? `${(dashRepo.size / 1024).toFixed(1)}MB` : `${dashRepo.size}KB` },
                ].map(s => (
                  <div key={s.label} style={{ display: 'flex', flexDirection: 'column', gap: 2, padding: '10px 14px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', minWidth: 80 }}>
                    <div style={{ fontSize: 10, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.4px' }}>{s.label}</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>{s.value}</div>
                  </div>
                ))}
              </div>

              {dashLoading ? (
                <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-faint)', fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                  <Icon name="loader" size={14} /> Loading repository details...
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
                  {/* Languages */}
                  {Object.keys(languages).length > 0 && (
                    <DashCard title="Languages" icon="file">
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {Object.entries(languages).slice(0, 5).map(([lang, bytes]) => {
                          const pct = Math.round((bytes / totalLangBytes) * 100)
                          return (
                            <div key={lang} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <div style={{ width: 8, height: 8, borderRadius: '50%', background: LANG_COLORS[lang] || LANG_COLORS.default, flexShrink: 0 }} />
                              <span style={{ fontSize: 12, color: 'var(--text-muted)', flex: 1 }}>{lang}</span>
                              <div style={{ width: 60, height: 4, background: 'var(--bg-elevated)', borderRadius: 2, overflow: 'hidden' }}>
                                <div style={{ width: `${pct}%`, height: '100%', background: LANG_COLORS[lang] || LANG_COLORS.default }} />
                              </div>
                              <span style={{ fontSize: 11, color: 'var(--text-faint)', width: 28, textAlign: 'right' }}>{pct}%</span>
                            </div>
                          )
                        })}
                      </div>
                    </DashCard>
                  )}

                  {/* Branches */}
                  <DashCard title={`Branches (${branches.length})`} icon="git">
                    {branches.length === 0 ? <Empty /> : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {branches.slice(0, 6).map((b: any) => (
                          <div key={b.name} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                            <Icon name="git" size={11} style={{ color: 'var(--text-faint)' }} />
                            <span style={{ color: b.name === dashRepo.default_branch ? 'var(--accent-hover)' : 'var(--text-muted)', fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{b.name}</span>
                            {b.protected && <span style={{ fontSize: 9, color: 'var(--warning)', background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 8, padding: '1px 5px' }}>protected</span>}
                            {b.name === dashRepo.default_branch && <span style={{ fontSize: 9, color: 'var(--accent-hover)', background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 8, padding: '1px 5px' }}>default</span>}
                          </div>
                        ))}
                        {branches.length > 6 && <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 2 }}>+{branches.length - 6} more</div>}
                      </div>
                    )}
                  </DashCard>

                  {/* Open Issues */}
                  <DashCard title={`Open Issues (${issues.length})`} icon="info">
                    {issues.length === 0 ? <Empty text="No open issues" /> : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {issues.slice(0, 4).map((issue: any) => (
                          <a key={issue.number} href={issue.html_url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'none', display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                            <span style={{ fontSize: 11, color: 'var(--text-faint)', fontFamily: 'monospace', flexShrink: 0, marginTop: 1 }}>#{issue.number}</span>
                            <span style={{ fontSize: 12, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{issue.title}</span>
                          </a>
                        ))}
                        {issues.length > 4 && <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 2 }}>+{issues.length - 4} more open</div>}
                      </div>
                    )}
                  </DashCard>

                  {/* Pull Requests */}
                  <DashCard title={`Pull Requests (${prs.length})`} icon="send">
                    {prs.length === 0 ? <Empty text="No open PRs" /> : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {prs.slice(0, 4).map((pr: any) => (
                          <a key={pr.number} href={pr.html_url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'none', display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                            <span style={{ fontSize: 11, color: 'var(--accent-hover)', fontFamily: 'monospace', flexShrink: 0, marginTop: 1 }}>#{pr.number}</span>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ fontSize: 12, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{pr.title}</div>
                              <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>{pr.head} → {pr.base} {pr.draft && '· Draft'}</div>
                            </div>
                          </a>
                        ))}
                        {prs.length > 4 && <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 2 }}>+{prs.length - 4} more open</div>}
                      </div>
                    )}
                  </DashCard>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function RepoCard({ repo, onOpen, onSelect, isActive }: { repo: Repo; onOpen: () => void; onSelect: () => void; isActive: boolean }) {
  const langColor = LANG_COLORS[repo.language] || LANG_COLORS.default
  return (
    <div
      onClick={onOpen}
      style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12, transition: 'background 0.1s', background: isActive ? 'rgba(99,102,241,0.06)' : 'transparent' }}
      onMouseEnter={e => { if (!isActive) (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.03)' }}
      onMouseLeave={e => { if (!isActive) (e.currentTarget as HTMLElement).style.background = 'transparent' }}
    >
      <img src={repo.owner_avatar} alt="" style={{ width: 28, height: 28, borderRadius: '50%', flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: isActive ? 'var(--accent-hover)' : 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {repo.name}
          </span>
          {repo.private && <span style={{ fontSize: 9, color: 'var(--text-faint)', background: 'rgba(255,255,255,0.06)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: '1px 6px', flexShrink: 0 }}>Private</span>}
          {repo.fork && <span style={{ fontSize: 9, color: 'var(--text-faint)', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: '1px 6px', flexShrink: 0 }}>Fork</span>}
          {repo.archived && <span style={{ fontSize: 9, color: 'var(--warning)', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 8, padding: '1px 6px', flexShrink: 0 }}>Archived</span>}
        </div>
        {repo.description && <div style={{ fontSize: 12, color: 'var(--text-faint)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginBottom: 4 }}>{repo.description}</div>}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {repo.language && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'var(--text-faint)' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: langColor }} />
              {repo.language}
            </span>
          )}
          {repo.stargazers_count > 0 && <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>★ {repo.stargazers_count}</span>}
          <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>{timeAgo(repo.pushed_at)}</span>
        </div>
      </div>
      <button
        onClick={e => { e.stopPropagation(); onSelect() }}
        style={{ fontSize: 11, color: 'var(--accent-hover)', background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.25)', borderRadius: 'var(--radius-sm)', padding: '4px 10px', cursor: 'pointer', fontWeight: 600, flexShrink: 0, whiteSpace: 'nowrap' }}
      >
        Use
      </button>
    </div>
  )
}

function DashCard({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '14px 16px' }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 5 }}>
        <Icon name={icon as any} size={11} /> {title}
      </div>
      {children}
    </div>
  )
}

function Empty({ text = 'Nothing here yet' }: { text?: string }) {
  return <div style={{ fontSize: 12, color: 'var(--text-faint)', textAlign: 'center', padding: '8px 0' }}>{text}</div>
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-faint)' }}>{label}</label>
      {children}
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-md)',
  padding: '8px 12px',
  color: 'var(--text)',
  fontSize: 13,
  outline: 'none',
  boxSizing: 'border-box',
}
