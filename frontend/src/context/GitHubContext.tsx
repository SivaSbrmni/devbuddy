import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'

const BACKEND = import.meta.env.VITE_API_URL || ''
const API = `${BACKEND}/api/v1`

export interface Repo {
  id: number
  full_name: string
  name: string
  owner: string
  owner_avatar: string
  description: string
  private: boolean
  language: string
  stargazers_count: number
  forks_count: number
  open_issues_count: number
  default_branch: string
  updated_at: string
  pushed_at: string
  html_url: string
  clone_url: string
  size: number
  topics: string[]
  visibility: string
  fork: boolean
  archived: boolean
}

interface GitHubCtx {
  connected: boolean
  githubLogin: string | null
  loading: boolean
  connect: () => void
  disconnect: () => void
  repos: Repo[]
  reposLoading: boolean
  fetchRepos: () => Promise<void>
  searchRepos: (q: string) => Promise<Repo[]>
  activeRepo: Repo | null
  setActiveRepo: (r: Repo | null) => void
}

const Ctx = createContext<GitHubCtx>({} as GitHubCtx)

export function GitHubProvider({ children, token }: { children: ReactNode; token: string }) {
  const [connected, setConnected] = useState(false)
  const [githubLogin, setGithubLogin] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [repos, setRepos] = useState<Repo[]>([])
  const [reposLoading, setReposLoading] = useState(false)
  const [activeRepo, setActiveRepoState] = useState<Repo | null>(() => {
    try { return JSON.parse(localStorage.getItem('devbuddy_active_repo') || 'null') } catch { return null }
  })

  const setActiveRepo = useCallback((r: Repo | null) => {
    setActiveRepoState(r)
    if (r) localStorage.setItem('devbuddy_active_repo', JSON.stringify(r))
    else localStorage.removeItem('devbuddy_active_repo')
  }, [])

  useEffect(() => {
    if (!token) { setLoading(false); return }
    fetch(`${API}/github/status?token=${encodeURIComponent(token)}`)
      .then(r => r.ok ? r.json() : { connected: false })
      .then(d => { setConnected(d.connected); setGithubLogin(d.login || null) })
      .catch(() => { setConnected(false) })
      .finally(() => setLoading(false))
  }, [token])

  const connect = useCallback(() => {
    window.location.href = `${API}/github/login?token=${encodeURIComponent(token)}`
  }, [token])

  const disconnect = useCallback(() => {
    setConnected(false)
    setGithubLogin(null)
    setRepos([])
    setActiveRepo(null)
  }, [setActiveRepo])

  const fetchRepos = useCallback(async () => {
    if (!connected) return
    setReposLoading(true)
    try {
      const r = await fetch(`${API}/github/repos?token=${encodeURIComponent(token)}&per_page=50&sort=pushed`)
      if (r.ok) setRepos(await r.json())
    } finally {
      setReposLoading(false)
    }
  }, [connected, token])

  const searchRepos = useCallback(async (q: string): Promise<Repo[]> => {
    if (!q.trim()) return repos
    const r = await fetch(`${API}/github/repos/search?token=${encodeURIComponent(token)}&q=${encodeURIComponent(q)}`)
    if (r.ok) return r.json()
    return []
  }, [token, repos])

  useEffect(() => {
    if (connected) fetchRepos()
  }, [connected])

  return (
    <Ctx.Provider value={{ connected, githubLogin, loading, connect, disconnect, repos, reposLoading, fetchRepos, searchRepos, activeRepo, setActiveRepo }}>
      {children}
    </Ctx.Provider>
  )
}

export const useGitHub = () => useContext(Ctx)
