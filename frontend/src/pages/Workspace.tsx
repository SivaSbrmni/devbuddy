import { useState, useRef, useEffect, useCallback } from 'react'
import { useAuth } from '../context/AuthContext'
import { GitHubProvider, useGitHub } from '../context/GitHubContext'
import GitHubPanel from '../components/GitHubPanel'
import AgentTimeline, { AgentRun, TimelineStep } from '../components/AgentTimeline'
import TaskCard, { TaskCardData, TaskEvent, sseToTaskEvent } from '../components/TaskCard'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import JSZip from 'jszip'
import ToastContainer, { toast } from '../components/Toast'
import Skeleton, { MessageSkeleton, TypingIndicator } from '../components/Skeleton'
import CommandPalette from '../components/CommandPalette'
import WorkspacePanel from '../components/WorkspacePanel'
import ContextBar from '../components/ContextBar'
import Icon from '../components/Icon'
import Dropdown from '../components/Dropdown'

const BACKEND = import.meta.env.VITE_API_URL || ''
const API = `${BACKEND}/api/v1`

function capitalizeFirst(s: string): string {
  if (!s) return s
  return s.charAt(0).toUpperCase() + s.slice(1)
}

interface Model {
  id: string
  label: string
  provider: string
  family: string
}

const FALLBACK_MODELS: Model[] = [
  { id: 'claude-sonnet-4-20250514', label: 'Claude Sonnet 4', provider: 'anthropic', family: 'anthropic' },
  { id: 'llama-4-scout-17b-16e-instruct', label: 'Llama 4 Scout', provider: 'llama', family: 'llama' },
  { id: 'qwen3-coder:480b', label: 'Qwen 3 Coder', provider: 'ollama', family: 'ollama' },
  { id: 'llama3.3:latest', label: 'Llama 3.3', provider: 'ollama', family: 'ollama' },
  { id: 'deepseek-coder:latest', label: 'DeepSeek Coder', provider: 'ollama', family: 'ollama' },
]

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  ts: number
  steps?: string[]
  files?: { name: string; content: string }[]
  agentEvents?: AgentEvent[]
  taskCard?: TaskCardData
}

interface AgentEvent {
  type: 'step' | 'file' | 'command' | 'test' | 'review' | 'workspace' | 'artifact' | 'done' | 'error'
  timestamp: number
  payload: any
}

interface Conversation {
  id: string
  title: string
  messages: Message[]
  ts: number
}

function newConv(): Conversation {
  return { id: crypto.randomUUID(), title: 'New conversation', messages: [], ts: Date.now() }
}

function useConversations() {
  const [convs, setConvs] = useState<Conversation[]>(() => {
    try { return JSON.parse(localStorage.getItem('devbuddy_convs') || '[]') } catch { return [] }
  })
  const [activeId, setActiveId] = useState<string>(() => {
    const stored = JSON.parse(localStorage.getItem('devbuddy_convs') || '[]')
    return stored[0]?.id || ''
  })

  const save = (list: Conversation[]) => {
    setConvs(list)
    localStorage.setItem('devbuddy_convs', JSON.stringify(list))
  }

  const active = convs.find(c => c.id === activeId) || null

  const createNew = () => {
    const c = newConv()
    const list = [c, ...convs]
    save(list)
    setActiveId(c.id)
    return c
  }

  const updateActive = (msgs: Message[] | ((prev: Message[]) => Message[]), title?: string, forceId?: string) => {
    const targetId = forceId ?? activeId
    setConvs(prev => {
      const list = prev.map(c => {
        if (c.id !== targetId) return c
        const next = typeof msgs === 'function' ? msgs(c.messages) : msgs
        return { ...c, messages: next, title: title || c.title, ts: Date.now() }
      })
      localStorage.setItem('devbuddy_convs', JSON.stringify(list))
      return list
    })
  }

  const selectConv = (id: string) => setActiveId(id)

  const deleteConv = (id: string) => {
    const list = convs.filter(c => c.id !== id)
    save(list)
    if (activeId === id) setActiveId(list[0]?.id || '')
  }

  const restoreConv = (conv: Conversation) => {
    save([conv, ...convs])
    setActiveId(conv.id)
  }

  return { convs, active, activeId, createNew, updateActive, selectConv, deleteConv, restoreConv }
}

export default function Workspace() {
  const { user, logout } = useAuth()
  const { convs, active, activeId, createNew, updateActive, selectConv, deleteConv, restoreConv } = useConversations()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [githubPanelOpen, setGithubPanelOpen] = useState(false)
  const [activeRepo, setActiveRepoLocal] = useState<{ name: string; owner: string; full_name: string; html_url: string; default_branch?: string } | null>(() => {
    try { return JSON.parse(localStorage.getItem('devbuddy_active_repo') || 'null') } catch { return null }
  })
  const [agentRun, setAgentRun] = useState<AgentRun | null>(null)
  const [agentTimelineOpen, setAgentTimelineOpen] = useState(false)
  const [models, setModels] = useState<Model[]>(FALLBACK_MODELS)
  const [modelsLoading, setModelsLoading] = useState(true)
  const [model, setModel] = useState(FALLBACK_MODELS[0].id)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [workspaceOpen, setWorkspaceOpen] = useState(false)
  const [agentMode, setAgentMode] = useState(true)
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [workspaceFiles, setWorkspaceFiles] = useState<string[]>([])
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [mentionOpen, setMentionOpen] = useState(false)
  const [mentionQuery, setMentionQuery] = useState('')
  const [mentionIndex, setMentionIndex] = useState(0)
  const [aiThinking, setAiThinking] = useState(false)
  const [aiReasoning, setAiReasoning] = useState<string | null>(null)
  const [providerKeys, setProviderKeys] = useState({
    anthropic: { key: '', base_url: '' },
    ollama: { key: '', base_url: '' },
    llama: { key: '', base_url: '' },
  })
  const [savingKeys, setSavingKeys] = useState(false)
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768)
  const [lastDeleted, setLastDeleted] = useState<Conversation | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const messages = active?.messages || []

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Auto-open workspace when files are generated (but respect manual close)
  useEffect(() => {
    if (workspaceFiles.length > 0 && !workspaceOpen) {
      // Small delay so it doesn't feel jarring during streaming
      const timer = setTimeout(() => setWorkspaceOpen(true), 300)
      return () => clearTimeout(timer)
    }
  }, [workspaceFiles.length])

  useEffect(() => {
    if (!activeId && !loading) createNew()
  }, [])

  // Handle GitHub OAuth callback — refresh token if github_connected param present
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const newToken = params.get('token')
    const ghConnected = params.get('github_connected')
    if (newToken && ghConnected) {
      localStorage.setItem('devbuddy_token', newToken)
      window.history.replaceState({}, '', window.location.pathname)
      window.location.reload()
    }
  }, [])

  // Fetch models and user settings on mount
  useEffect(() => {
    const token = localStorage.getItem('devbuddy_token') || ''

    const fetchModels = async () => {
      try {
        setModelsLoading(true)
        const resp = await fetch(`${API}/models?token=${encodeURIComponent(token)}`)
        if (resp.ok) {
          const data = await resp.json()
          setModels(data.length > 0 ? data : [])
          if (data.length > 0) {
            setModel(prev => data.find((m: Model) => m.id === prev) ? prev : data[0].id)
          }
        }
      } catch (e) {
        console.error('Failed to fetch models:', e)
      } finally {
        setModelsLoading(false)
      }
    }

    const fetchSettings = async () => {
      try {
        const resp = await fetch(`${API}/settings?token=${encodeURIComponent(token)}`)
        if (resp.ok) {
          const data = await resp.json()
          const p = data.providers || {}
          setProviderKeys({
            anthropic: { key: p.anthropic?.configured ? '••••••••' : '', base_url: p.anthropic?.base_url || '' },
            ollama: { key: p.ollama?.configured ? '••••••••' : '', base_url: p.ollama?.base_url || '' },
            llama: { key: p.llama?.configured ? '••••••••' : '', base_url: p.llama?.base_url || '' },
          })
        }
      } catch (e) {
        console.error('Failed to fetch settings:', e)
      }
    }

    fetchModels()
    fetchSettings()
  }, [])

  // Cmd+K command palette
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setPaletteOpen(prev => !prev)
      }
      if (e.key === 'Escape') {
        setPaletteOpen(false)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  const saveProviderKeys = async () => {
    const token = localStorage.getItem('devbuddy_token') || ''
    setSavingKeys(true)
    try {
      const payload: any = {}
      for (const id of ['anthropic', 'ollama', 'llama'] as const) {
        const { key, base_url } = providerKeys[id]
        const hasNewKey = key && key !== '••••••••'
        const hasUrl = base_url.trim() !== ''
        if (hasNewKey || hasUrl) {
          payload[id] = {
            ...(hasNewKey ? { key } : {}),
            base_url,
          }
        }
      }

      const resp = await fetch(`${API}/settings?token=${encodeURIComponent(token)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (resp.ok) {
        toast('API keys saved successfully', 'success')
        // Refresh models after saving keys
        const modelsResp = await fetch(`${API}/models?token=${encodeURIComponent(token)}`)
        if (modelsResp.ok) {
          const data = await modelsResp.json()
          setModels(data)
          if (data.length > 0) setModel(data[0].id)
        }
        setSettingsOpen(false)
      } else {
        toast('Failed to save API keys', 'error')
      }
    } catch (e) {
      console.error('Failed to save keys:', e)
      toast('Failed to save API keys', 'error')
    } finally {
      setSavingKeys(false)
    }
  }

  const runGitHubAgent = useCallback(async (task: string, msgId: string, conversationAtStart: Message[]) => {
    if (!activeRepo) return false
    const token = localStorage.getItem('devbuddy_token') || ''
    const owner = (activeRepo as any).owner || activeRepo.full_name?.split('/')[0] || ''
    const repo = activeRepo.name

    const cardId = msgId
    const initialCard: TaskCardData = {
      id: cardId,
      task,
      repo: `${owner}/${repo}`,
      branch: '',
      startedAt: Date.now(),
      status: 'running',
      progress: 2,
      currentTool: 'Connecting to repository…',
      events: [],
      isGitHubTask: true,
    }

    // Inject a synthetic assistant message that holds the TaskCard
    const agentMsg: Message = {
      id: cardId,
      role: 'assistant',
      content: '',
      ts: Date.now(),
      taskCard: initialCard,
    }

    const convTitle = conversationAtStart.length === 1 ? capitalizeFirst(task.slice(0, 50)) : (active?.title || capitalizeFirst(task.slice(0, 50)))
    updateActive([...conversationAtStart, agentMsg], convTitle)

    // Helper: patch the taskCard of the agent message in-place
    const patchCard = (fn: (c: TaskCardData) => TaskCardData) => {
      updateActive(prev => prev.map(m => m.id === cardId && m.taskCard
        ? { ...m, taskCard: fn(m.taskCard) }
        : m
      ), convTitle)
    }

    // Progress map by timeline step
    const PROGRESS: Record<string, number> = {
      init: 8, workspace: 18, branch: 28, analysis: 38,
      planning: 48, execution: 62, commit: 82, push: 90, pr: 96,
    }


    try {
      const resp = await fetch(`${API}/github-agent/run?token=${encodeURIComponent(token)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, owner, repo, conversation_id: activeId }),
      })
      if (!resp.ok) {
        const err = await resp.text()
        patchCard(c => ({ ...c, status: 'error', currentTool: undefined,
          events: [...c.events, { id: 'err', ts: Date.now(), category: 'error', title: err.slice(0, 120), status: 'error' } as TaskEvent] }))
        return true
      }

      const reader = resp.body!.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const evt = JSON.parse(line.slice(6))
            const { type, payload } = evt

            // Convert to TaskEvent
            const taskEvt = sseToTaskEvent(type, payload)

            patchCard(c => {
              const next = { ...c }

              // Complete the last 'running' tool_call when observation arrives
              if (type === 'observation') {
                next.events = next.events.map(e =>
                  e.category === 'tool' && e.status === 'running' ? { ...e, status: 'done' } : e
                )
              }

              // Patch running timeline events to done
              if (type === 'timeline' && payload.status === 'done') {
                next.events = next.events.map(e =>
                  e.category === (payload.step as any) && e.status === 'running' ? { ...e, status: 'done', title: payload.message } : e
                )
              }

              if (taskEvt) next.events = [...next.events, taskEvt]

              // Update progress
              if (type === 'timeline' && PROGRESS[payload.step]) {
                next.progress = Math.max(next.progress, PROGRESS[payload.step])
              }

              // Update current tool label
              if (type === 'tool_call') next.currentTool = `${payload.tool.replace('_', ' ')} ${Object.values(payload.params || {})[0]?.toString().slice(0, 30) ?? ''}`
              if (type === 'timeline' && payload.status === 'running') next.currentTool = payload.message

              // Branch
              if (type === 'branch') next.branch = payload.name || ''

              // PR
              if (type === 'pr') { next.prUrl = payload.url || ''; next.prNumber = payload.number || '' }

              // File
              if (type === 'file_change' && payload.path) {
                const mf = next.modifiedFiles || []
                if (!mf.includes(payload.path)) next.modifiedFiles = [...mf, payload.path]
              }

              // Done
              if (type === 'done') {
                next.status = 'done'
                next.progress = 100
                next.currentTool = undefined
                next.prUrl = payload.pr_url || next.prUrl
                next.commitHash = payload.commit_hash || ''
                if (payload.modified_files?.length) next.modifiedFiles = payload.modified_files
              }

              // Error
              if (type === 'error') {
                next.status = 'error'
                next.currentTool = undefined
              }

              return next
            })

          } catch (_) {}
        }
      }
    } catch (e: any) {
      patchCard(c => ({ ...c, status: 'error', currentTool: undefined,
        events: [...c.events, { id: 'err', ts: Date.now(), category: 'error', title: e.message, status: 'error' } as TaskEvent] }))
    }
    return true
  }, [activeRepo, activeId, active?.title])

  const runCloudAgent = useCallback(async (task: string, msgId: string, conversationAtStart: Message[], convId?: string) => {
    if (!activeRepo) return false
    const token = localStorage.getItem('devbuddy_token') || ''
    const owner = (activeRepo as any).owner || activeRepo.full_name?.split('/')[0] || ''
    const repo = activeRepo.name

    const cardId = msgId
    const initialCard: TaskCardData = {
      id: cardId,
      task,
      repo: `${owner}/${repo}`,
      branch: '',
      startedAt: Date.now(),
      status: 'running',
      progress: 2,
      currentTool: 'Dispatching GitHub Actions runner…',
      events: [],
      isGitHubTask: true,
      isCloudJob: true,
      runnerState: 'queued',
    }

    const agentMsg: Message = {
      id: cardId,
      role: 'assistant',
      content: '',
      ts: Date.now(),
      taskCard: initialCard,
    }

    const convTitle = conversationAtStart.length === 1 ? capitalizeFirst(task.slice(0, 50)) : (active?.title || capitalizeFirst(task.slice(0, 50)))
    updateActive([...conversationAtStart, agentMsg], convTitle, convId)

    const patchCard = (fn: (c: TaskCardData) => TaskCardData) => {
      updateActive(prev => prev.map(m => m.id === cardId && m.taskCard
        ? { ...m, taskCard: fn(m.taskCard) }
        : m
      ), convTitle, convId)
    }

    const PROGRESS: Record<string, number> = {
      queued: 4, provisioning: 12, initializing: 20, connecting: 30,
      analyzing: 40, executing: 55, validating: 72, reflecting: 80,
      pushing: 88, creating_pr: 94, uploading: 97, completed: 100,
    }

    try {
      const resp = await fetch(`${API}/cloud-agent/run?token=${encodeURIComponent(token)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, owner, repo, conversation_id: activeId }),
      })
      if (!resp.ok) {
        const err = await resp.text()
        patchCard(c => ({ ...c, status: 'error', currentTool: undefined,
          events: [...c.events, { id: 'err', ts: Date.now(), category: 'error', title: err.slice(0, 160), status: 'error' } as TaskEvent] }))
        return true
      }

      const reader = resp.body!.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const evt = JSON.parse(line.slice(6))
            const { type, payload } = evt
            const taskEvt = sseToTaskEvent(type, payload)

            patchCard(c => {
              const next = { ...c }

              if (type === 'observation') {
                next.events = next.events.map(e =>
                  e.category === 'tool' && e.status === 'running' ? { ...e, status: 'done' } : e
                )
              }

              if (taskEvt && type !== 'runner') next.events = [...next.events, taskEvt]

              if (type === 'runner') {
                const state = payload.state
                next.runnerState = state
                next.runUrl = payload.run_url || next.runUrl
                next.runId = payload.run_id || next.runId
                if (PROGRESS[state]) next.progress = Math.max(next.progress, PROGRESS[state])
                next.currentTool = payload.message || state
                const evt2 = sseToTaskEvent(type, payload)
                if (evt2) next.events = [...next.events, evt2]
              }

              if (type === 'quality_gates') {
                next.qualityGates = { ...(next.qualityGates || {}), ...payload.gates }
              }

              if (type === 'timeline' && PROGRESS[payload.step]) {
                next.progress = Math.max(next.progress, PROGRESS[payload.step] || 0)
              }

              if (type === 'branch') next.branch = payload.name || ''
              if (type === 'pr') { next.prUrl = payload.url || ''; next.prNumber = payload.number || '' }
              if (type === 'file_change' && payload.path) {
                const mf = next.modifiedFiles || []
                if (!mf.includes(payload.path)) next.modifiedFiles = [...mf, payload.path]
              }
              if (type === 'done') {
                next.status = 'done'; next.progress = 100; next.currentTool = undefined
                next.prUrl = payload.pr_url || next.prUrl
                next.commitHash = payload.commit_hash || ''
                next.runUrl = payload.run_url || next.runUrl
                next.qualityGates = payload.quality_gates ? { ...(next.qualityGates || {}), ...payload.quality_gates } : next.qualityGates
                if (payload.modified_files?.length) next.modifiedFiles = payload.modified_files
              }
              if (type === 'error') { next.status = 'error'; next.currentTool = undefined }
              return next
            })
          } catch (_) {}
        }
      }
    } catch (e: any) {
      patchCard(c => ({ ...c, status: 'error', currentTool: undefined,
        events: [...c.events, { id: 'err', ts: Date.now(), category: 'error', title: e.message, status: 'error' } as TaskEvent] }))
    }
    return true
  }, [activeRepo, activeId, active?.title])

  const autoResize = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }

  const processSSEStream = async (
    reader: ReadableStreamDefaultReader<Uint8Array>,
    onChunk: (line: string) => void
  ) => {
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop() ?? ''
      for (const line of lines) onChunk(line)
    }
    if (buf) onChunk(buf)
  }

  const sendChat = async (newMsgs: Message[], assistantMsg: Message, title: string) => {
    const resp = await fetch(`${API}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: newMsgs.map(m => ({ role: m.role, content: m.content })),
        model,
      }),
      signal: abortControllerRef.current!.signal,
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const reader = resp.body?.getReader()
    if (!reader) return
    let fullContent = ''
    await processSSEStream(reader, (line) => {
      if (!line.startsWith('data: ')) return
      const data = line.slice(6)
      if (data === '[DONE]') return
      if (data.startsWith('[ERROR]')) throw new Error(data.slice(7))
      if (data.startsWith('[STEP]')) {
        assistantMsg.steps = [...(assistantMsg.steps || []), data.slice(7)]
        updateActive([...newMsgs, { ...assistantMsg }], title)
      } else if (data.startsWith('[FILE]')) {
        try {
          const fileData = JSON.parse(data.slice(6))
          assistantMsg.files = [...(assistantMsg.files || []), fileData]
          updateActive([...newMsgs, { ...assistantMsg }], title)
        } catch {}
      } else {
        fullContent += data
        updateActive([...newMsgs, { ...assistantMsg, content: fullContent }], title)
      }
    })
  }

  const sendAgent = async (text: string, newMsgs: Message[], assistantMsg: Message, title: string) => {
    const resp = await fetch(`${API}/agent/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: text, model }),
      signal: abortControllerRef.current!.signal,
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const reader = resp.body?.getReader()
    if (!reader) return
    let summaryContent = ''
    await processSSEStream(reader, (line) => {
      if (!line.startsWith('data: ')) return
      let raw = line.slice(6).trim()
      if (!raw || raw === '[DONE]') return
      try {
        const event: AgentEvent = JSON.parse(raw)
        assistantMsg.agentEvents = [...(assistantMsg.agentEvents || []), event]
        if (event.type === 'step') {
          assistantMsg.steps = [...(assistantMsg.steps || []), event.payload?.message || event.payload?.agent || '']
        } else if (event.type === 'file') {
          const f = event.payload
          if (f?.path && f?.content !== undefined) {
            assistantMsg.files = [...(assistantMsg.files || []), { name: f.path, content: f.content }]
            setWorkspaceFiles(prev => prev.includes(f.path) ? prev : [...prev, f.path])
          }
        } else if (event.type === 'workspace') {
          if (event.payload?.workspace_id) setWorkspaceId(event.payload.workspace_id)
          if (event.payload?.files) setWorkspaceFiles(event.payload.files)
        } else if (event.type === 'done') {
          summaryContent = event.payload?.summary || event.payload?.message || 'Agent completed.'
          assistantMsg.content = summaryContent
        } else if (event.type === 'error') {
          assistantMsg.content = `Agent error: ${event.payload?.message || 'Unknown error'}`
        }
        updateActive([...newMsgs, { ...assistantMsg }], title)
      } catch {}
    })
    if (!assistantMsg.content) assistantMsg.content = summaryContent || 'Agent run complete.'
    updateActive([...newMsgs, { ...assistantMsg }], title)
  }

  // Auto-detect mode from prompt keywords
  const detectMode = (text: string): boolean => {
    const agentKeywords = ['build', 'create', 'setup', 'deploy', 'generate', 'make', 'scaffold', 'implement', 'write', 'develop']
    const chatKeywords = ['explain', 'why', 'how does', 'what is', 'compare', 'debug', 'fix', 'review', 'check']
    const lower = text.toLowerCase()
    const agentScore = agentKeywords.filter(k => lower.includes(k)).length
    const chatScore = chatKeywords.filter(k => lower.includes(k)).length
    if (agentScore > chatScore) return true
    if (chatScore > agentScore) return false
    return agentMode // default to current mode if ambiguous
  }

  // Auto-route to best model based on prompt content
  const routeModel = (text: string) => {
    const lower = text.toLowerCase()
    // Claude excels at code generation and structured tasks
    const claudeKeywords = ['build', 'create', 'implement', 'write', 'code', 'api', 'function', 'component', 'script', 'fastapi', 'react', 'vue', 'angular']
    // GPT-4 excels at reasoning and analysis
    const gptKeywords = ['explain', 'analyze', 'compare', 'why', 'how', 'review', 'debug', 'optimize', 'refactor']
    const claudeScore = claudeKeywords.filter(k => lower.includes(k)).length
    const gptScore = gptKeywords.filter(k => lower.includes(k)).length
    if (claudeScore > gptScore) {
      const claude = models.find(m => m.family === 'claude')
      if (claude) return claude.id
    }
    if (gptScore > claudeScore) {
      const gpt = models.find(m => m.family === 'gpt')
      if (gpt) return gpt.id
    }
    return model // keep current if ambiguous
  }

  const send = async () => {
    const text = input.trim()
    if (!text || loading) return

    // If a GitHub repo is active and agent mode is on → always cloud
    if (activeRepo && agentMode) {
      setInput('')
      if (textareaRef.current) textareaRef.current.style.height = 'auto'
      let conv = active
      let convId = activeId
      if (!conv) {
        conv = createNew()
        convId = conv.id
      }
      const userMsg: Message = { id: crypto.randomUUID(), role: 'user', content: text, ts: Date.now() }
      const agentMsgId = crypto.randomUUID()
      const msgsWithUser = [...conv.messages, userMsg]
      updateActive(msgsWithUser, capitalizeFirst(text.slice(0, 50)), convId)
      await runCloudAgent(text, agentMsgId, msgsWithUser, convId)
      return
    }

    // Auto-detect agent vs chat mode
    const shouldUseAgent = detectMode(text)
    if (shouldUseAgent !== agentMode) {
      setAgentMode(shouldUseAgent)
      toast(`Switched to ${shouldUseAgent ? 'Agent' : 'Chat'} mode`, 'info')
    }

    // Auto-route to best model
    const bestModel = routeModel(text)
    if (bestModel !== model) {
      setModel(bestModel)
      const m = models.find(x => x.id === bestModel)
      if (m) toast(`Using ${m.label}`, 'info')
    }

    let conv = active
    if (!conv) conv = createNew()

    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', content: text, ts: Date.now() }
    const title = conv.messages.length === 0 ? capitalizeFirst(text.slice(0, 50)) : conv.title
    const newMsgs = [...conv.messages, userMsg]
    updateActive(newMsgs, title)
    setInput('')
    setLoading(true)
    setAiThinking(true)
    setAiReasoning(agentMode ? 'Planning autonomous pipeline...' : 'Analyzing your question...')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'

    abortControllerRef.current = new AbortController()
    const assistantMsg: Message = { id: crypto.randomUUID(), role: 'assistant', content: '', ts: Date.now(), steps: [], files: [], agentEvents: [] }
    updateActive([...newMsgs, assistantMsg], title)

    try {
      if (agentMode) {
        await sendAgent(text, newMsgs, assistantMsg, title)
      } else {
        await sendChat(newMsgs, assistantMsg, title)
      }
    } catch (e) {
      const errorMsg = e instanceof Error && e.name === 'AbortError'
        ? 'Request cancelled'
        : `Error: ${e instanceof Error ? e.message : 'Failed to connect'}`
      updateActive([...newMsgs, { ...assistantMsg, content: errorMsg }], title)
    } finally {
      setLoading(false)
      setAiThinking(false)
      setAiReasoning(null)
      abortControllerRef.current = null
      if (active && active.messages.length > 2) {
        try {
          await fetch(`${API}/knowledge/extract`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              conversation_id: active.id,
              messages: active.messages.map(m => ({ role: m.role, content: m.content }))
            })
          })
        } catch (e) {
          console.error('Failed to extract knowledge:', e)
        }
      }
    }
  }

  const cancelRequest = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setLoading(false)
    setAiThinking(false)
    setAiReasoning(null)
    toast('Request cancelled', 'info')
  }

  // Mock project files for @ references
  const projectFiles = [
    'frontend/src/App.tsx',
    'frontend/src/pages/Workspace.tsx',
    'frontend/src/components/ContextBar.tsx',
    'frontend/src/components/Icon.tsx',
    'backend/app/main.py',
    'backend/app/api/routes/agent.py',
    'README.md',
    'package.json',
  ]

  const filteredMentions = mentionQuery
    ? projectFiles.filter(f => f.toLowerCase().includes(mentionQuery.toLowerCase()))
    : projectFiles

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (mentionOpen) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setMentionIndex(i => Math.min(i + 1, filteredMentions.length - 1))
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setMentionIndex(i => Math.max(i - 1, 0))
        return
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault()
        const file = filteredMentions[mentionIndex]
        if (file) {
          const lastAt = input.lastIndexOf('@')
          if (lastAt >= 0) {
            const before = input.slice(0, lastAt)
            const after = input.slice(lastAt + 1 + mentionQuery.length)
            setInput(before + '@' + file + ' ' + after)
            setMentionOpen(false)
            setMentionQuery('')
          }
        }
        return
      }
      if (e.key === 'Escape') {
        setMentionOpen(false)
        setMentionQuery('')
        return
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value
    setInput(val)
    autoResize()

    // Detect @mention
    const lastAt = val.lastIndexOf('@')
    if (lastAt >= 0) {
      const afterAt = val.slice(lastAt + 1)
      const endIdx = afterAt.search(/[\s\n]/)
      const query = endIdx >= 0 ? afterAt.slice(0, endIdx) : afterAt
      if (!afterAt.includes(' ') && !afterAt.includes('\n')) {
        setMentionQuery(query)
        setMentionOpen(true)
        setMentionIndex(0)
      } else {
        setMentionOpen(false)
      }
    } else {
      setMentionOpen(false)
    }
  }

  const downloadFiles = async (files: { name: string; content: string }[]) => {
    const zip = new JSZip()
    files.forEach(file => {
      zip.file(file.name, file.content)
    })
    const blob = await zip.generateAsync({ type: 'blob' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `devbuddy-${Date.now()}.zip`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const CodeBlock = ({ children, className, ...props }: any) => {
    const match = /language-(\w+)/.exec(className || '')
    const language = match ? match[1] : 'text'
    const [copied, setCopied] = useState(false)
    const codeText = typeof children === 'string' ? children : ''
    const copyCode = () => {
      navigator.clipboard.writeText(codeText).then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      })
    }
    return (
      <div style={{ position: 'relative', marginTop: 10, marginBottom: 10 }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'var(--border-subtle)',
          border: '1px solid var(--border)',
          borderBottom: 'none',
          borderRadius: 'var(--radius-md) var(--radius-md) 0 0',
          padding: '6px 12px',
        }}>
          <div style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'monospace', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{language}</div>
          <button onClick={copyCode} className="db-btn" style={{ background: 'none', border: 'none', color: copied ? 'var(--success)' : 'var(--text-dim)', fontSize: 11, cursor: 'pointer', padding: '2px 8px', borderRadius: 'var(--radius-sm)', transition: 'all var(--transition-fast)', display: 'flex', alignItems: 'center', gap: 4 }} onMouseEnter={e => { if (!copied) e.currentTarget.style.color = 'var(--accent-hover)' }} onMouseLeave={e => { if (!copied) e.currentTarget.style.color = 'var(--text-dim)' }}>
            {copied ? '✓ Copied' : '⎘ Copy'}
          </button>
        </div>
        <pre style={{
          background: 'var(--bg)',
          border: '1px solid var(--border)',
          borderTop: 'none',
          borderRadius: '0 0 var(--radius-md) var(--radius-md)',
          padding: '14px',
          overflowX: 'auto',
          fontSize: 13,
          lineHeight: 1.6,
          color: 'var(--text-muted)',
          margin: 0
        }}>
          <code className={className} {...props}>{children}</code>
        </pre>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--bg)', color: 'var(--text)', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' }}>

      {/* ── Mobile overlay ── */}
      {/* Close user menu on outside click */}
      {userMenuOpen && (
        <div onClick={() => setUserMenuOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 99 }} />
      )}

      {sidebarOpen && isMobile && (
        <div 
          onClick={() => setSidebarOpen(false)}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.6)',
            backdropFilter: 'blur(4px)',
            zIndex: 40,
            animation: 'fadeIn 0.2s ease',
          }}
        />
      )}

      {/* ── Left sidebar with conversation list ── */}
      <div style={{
        width: 240,
        height: '100vh',
        background: 'var(--bg-elevated)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        alignItems: 'stretch',
        padding: '12px 0',
        gap: 0,
        position: isMobile ? 'fixed' : 'relative',
        left: isMobile ? (sidebarOpen ? 0 : -240) : 0,
        top: 0,
        bottom: 0,
        zIndex: 50,
        transition: 'left 0.3s ease',
        boxSizing: 'border-box',
      }}>
        {/* App logo + new chat */}
        <div style={{ padding: '4px 12px 8px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 28,
              height: 28,
              borderRadius: 8,
              background: 'linear-gradient(135deg, var(--accent), var(--accent-hover))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              boxShadow: '0 2px 8px rgba(99,102,241,0.35)',
            }}>
              <Icon name="sparkles" size={14} style={{ color: 'white' }} />
            </div>
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', letterSpacing: '-0.2px' }}>DevBuddy</span>
          </div>
          <button
            onClick={createNew}
            title="New conversation (Ctrl+N)"
            className="db-btn"
            style={{
              width: 28,
              height: 28,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 'var(--radius-md)',
              background: 'transparent',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-dim)',
              cursor: 'pointer',
              transition: 'all var(--transition-fast)',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(99,102,241,0.1)'; e.currentTarget.style.borderColor = 'rgba(99,102,241,0.3)'; e.currentTarget.style.color = 'var(--accent-hover)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'var(--border-subtle)'; e.currentTarget.style.color = 'var(--text-dim)' }}
          >
            <Icon name="plus" size={14} />
          </button>
        </div>

        {/* Conversations list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'stretch', flex: 1, minHeight: 0, overflowY: 'auto', overflowX: 'hidden', padding: '4px 12px', width: '100%' }}>
          {convs.length === 0 && (
            <div style={{ padding: '20px 8px', textAlign: 'center', color: 'var(--text-faint)', fontSize: 12 }}>
              No conversations yet
            </div>
          )}
          {convs.map(c => {
            const hue = c.title.split('').reduce((acc, ch) => acc + ch.charCodeAt(0), 0) % 360
            const isActive = c.id === activeId
            const firstUserMessage = c.messages.find(m => m.role === 'user')?.content || ''
            const description = firstUserMessage.substring(0, 40) + (firstUserMessage.length > 40 ? '...' : '') || 'New conversation'
            return (
              <div
                key={c.id}
                role="button"
                tabIndex={0}
                onClick={() => selectConv(c.id)}
                onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectConv(c.id) } }}
                title={c.title}
                className="db-btn conv-item"
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  borderRadius: 'var(--radius-md)',
                  background: isActive ? `hsla(${hue}, 70%, 55%, 0.15)` : 'transparent',
                  border: isActive ? `1px solid hsla(${hue}, 70%, 55%, 0.3)` : '1px solid transparent',
                  color: isActive ? `hsl(${hue}, 70%, 65%)` : 'var(--text)',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                  gap: 3,
                  fontSize: 12,
                  fontWeight: isActive ? 600 : 500,
                  transition: 'all var(--transition-fast)',
                  flexShrink: 0,
                  textAlign: 'left',
                  overflow: 'hidden',
                  position: 'relative',
                  boxSizing: 'border-box',
                }}
                onMouseEnter={e => {
                  if (!isActive) e.currentTarget.style.background = 'rgba(255,255,255,0.04)'
                  const btn = e.currentTarget.querySelector('.conv-del-btn') as HTMLElement
                  if (btn) btn.style.opacity = '1'
                }}
                onMouseLeave={e => {
                  if (!isActive) e.currentTarget.style.background = 'transparent'
                  const btn = e.currentTarget.querySelector('.conv-del-btn') as HTMLElement
                  if (btn) btn.style.opacity = '0'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', minWidth: 0 }}>
                  <span style={{
                    width: 24,
                    height: 24,
                    borderRadius: '50%',
                    background: isActive ? `hsl(${hue}, 70%, 55%)` : `hsl(${hue}, 50%, 30%)`,
                    color: 'white',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 10,
                    fontWeight: 700,
                    flexShrink: 0,
                  }}>
                    {c.title.charAt(0).toUpperCase()}
                  </span>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, minWidth: 0, fontSize: 13 }}>
                    {c.title}
                  </span>
                  {c.messages.length > 0 && (
                    <span style={{ fontSize: 10, color: 'var(--text-faint)', flexShrink: 0, background: 'rgba(255,255,255,0.06)', padding: '1px 5px', borderRadius: 'var(--radius-sm)', minWidth: 16, textAlign: 'center' }}>
                      {c.messages.length}
                    </span>
                  )}
                  <button
                    className="conv-del-btn"
                    onClick={e => {
                      e.stopPropagation()
                      setLastDeleted(c)
                      deleteConv(c.id)
                      setTimeout(() => setLastDeleted(null), 5000)
                    }}
                    title="Delete conversation"
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-faint)',
                      cursor: 'pointer',
                      padding: '2px 4px',
                      borderRadius: 'var(--radius-sm)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                      opacity: 0,
                      transition: 'all var(--transition-fast)',
                      lineHeight: 1,
                    }}
                    onMouseEnter={e => { e.currentTarget.style.color = 'var(--error)'; e.currentTarget.style.background = 'rgba(239,68,68,0.12)' }}
                    onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-faint)'; e.currentTarget.style.background = 'none' }}
                  >
                    <Icon name="trash" size={12} />
                  </button>
                </div>
                <span style={{ fontSize: 11, color: 'var(--text-faint)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', width: '100%', paddingLeft: 32 }}>
                  {description}
                </span>
              </div>
            )
          })}
        </div>

        {/* Undo delete toast */}
        {lastDeleted && (
          <div style={{ margin: '4px 12px', padding: '8px 12px', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, animation: 'fadeIn 0.15s ease', flexShrink: 0 }}>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, minWidth: 0 }}>Deleted <strong style={{ color: 'var(--text)' }}>{lastDeleted.title}</strong></span>
            <button
              onClick={() => { restoreConv(lastDeleted); setLastDeleted(null) }}
              style={{ fontSize: 11, color: 'var(--accent-hover)', background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.25)', borderRadius: 'var(--radius-sm)', padding: '3px 10px', cursor: 'pointer', fontWeight: 600, flexShrink: 0, whiteSpace: 'nowrap' }}
            >Undo</button>
          </div>
        )}

        {/* Bottom: user menu */}
        <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border-subtle)', position: 'relative' }}>
          <div
            role="button"
            tabIndex={0}
            onClick={() => setUserMenuOpen(v => !v)}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') setUserMenuOpen(v => !v) }}
            className="db-btn"
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px', borderRadius: 'var(--radius-md)', cursor: 'pointer', transition: 'background var(--transition-fast)', width: '100%' }}
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            {user?.picture ? (
              <img src={user.picture} alt={user?.name || 'User'} style={{ width: 28, height: 28, borderRadius: '50%', objectFit: 'cover', border: '2px solid var(--border)', flexShrink: 0 }} />
            ) : (
              <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--bg-card)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <Icon name="user" size={14} style={{ color: 'var(--text-dim)' }} />
              </div>
            )}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user?.name || 'User'}</div>
              <div style={{ fontSize: 10, color: 'var(--text-faint)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user?.email}</div>
            </div>
            <Icon name="command" size={12} style={{ color: 'var(--text-faint)', flexShrink: 0 }} />
          </div>
          {userMenuOpen && (
            <div
              style={{ position: 'absolute', bottom: '100%', left: 12, right: 12, marginBottom: 4, background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', boxShadow: '0 8px 24px rgba(0,0,0,0.4)', overflow: 'hidden', animation: 'fadeIn 0.12s ease', zIndex: 100 }}
            >
              <button onClick={() => { setPaletteOpen(true); setUserMenuOpen(false) }} className="db-btn" style={{ width: '100%', padding: '10px 14px', background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, textAlign: 'left', borderBottom: '1px solid var(--border-subtle)' }} onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.color = 'var(--text)' }} onMouseLeave={e => { e.currentTarget.style.background = 'none'; e.currentTarget.style.color = 'var(--text-muted)' }}>
                <Icon name="command" size={14} /> Commands
                <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-faint)', background: 'var(--bg-card)', padding: '1px 5px', borderRadius: 4, fontFamily: 'monospace' }}>⌘K</span>
              </button>
              <button onClick={() => { setSettingsOpen(true); setUserMenuOpen(false) }} className="db-btn" style={{ width: '100%', padding: '10px 14px', background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, textAlign: 'left', borderBottom: '1px solid var(--border-subtle)' }} onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.color = 'var(--text)' }} onMouseLeave={e => { e.currentTarget.style.background = 'none'; e.currentTarget.style.color = 'var(--text-muted)' }}>
                <Icon name="settings" size={14} /> API Keys
              </button>
              <button onClick={() => { logout(); setUserMenuOpen(false) }} className="db-btn" style={{ width: '100%', padding: '10px 14px', background: 'none', border: 'none', color: 'var(--error)', fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, textAlign: 'left' }} onMouseEnter={e => { e.currentTarget.style.background = 'rgba(239,68,68,0.06)' }} onMouseLeave={e => { e.currentTarget.style.background = 'none' }}>
                <Icon name="logout" size={14} /> Sign out
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ── Main chat area ── */}
      <div style={{ flex: 1, minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

        {/* Top bar — 2050 OS: minimal, contextual */}
        <div style={{ padding: '8px 16px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {/* Mobile menu */}
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="db-btn"
              style={{
                display: isMobile ? 'flex' : 'none',
                background: 'none',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                width: 32,
                height: 32,
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Icon name="menu" size={18} />
            </button>

            {/* Title + mode */}
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', maxWidth: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {active?.title || 'New conversation'}
            </div>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              background: agentMode ? 'rgba(16,185,129,0.08)' : 'transparent',
              border: agentMode ? '1px solid rgba(16,185,129,0.15)' : '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-full)',
              padding: '2px 8px',
            }}>
              <Icon name={agentMode ? 'agent' : 'chat'} size={10} />
              <span style={{ fontSize: 10, color: agentMode ? 'var(--success)' : 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{agentMode ? 'Agent' : 'Chat'}</span>
            </div>

            {/* AI Thinking indicator */}
            {aiThinking && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                animation: 'fadeIn 0.3s ease',
              }}>
                <span className="pulse" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)' }} />
                <span style={{ fontSize: 11, color: 'var(--accent-hover)', fontWeight: 500 }}>{aiReasoning}</span>
              </div>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {/* GitHub repo button */}
            <GitHubRepoButton activeRepo={activeRepo} onClick={() => setGithubPanelOpen(true)} />

            {/* Global search / command */}
            <button
              onClick={() => setPaletteOpen(true)}
              className="db-btn db-focus"
              style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-faint)',
                fontSize: 12,
                padding: '4px 10px',
                cursor: 'pointer',
                display: isMobile ? 'none' : 'flex',
                alignItems: 'center',
                gap: 6,
                minWidth: 140,
                justifyContent: 'flex-start',
              }}
            >
              <Icon name="command" size={12} />
              <span style={{ fontSize: 12 }}>Search...</span>
              <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-faint)', background: 'var(--bg-card)', padding: '1px 5px', borderRadius: 'var(--radius-sm)' }}>⌘K</span>
            </button>

            {/* Workspace toggle */}
            <button
              onClick={() => setWorkspaceOpen(!workspaceOpen)}
              className="db-btn db-focus"
              title="Toggle workspace"
              style={{
                background: workspaceOpen ? 'rgba(99,102,241,0.08)' : 'transparent',
                border: workspaceOpen ? '1px solid rgba(99,102,241,0.2)' : '1px solid transparent',
                borderRadius: 'var(--radius-md)',
                color: workspaceOpen ? 'var(--accent-hover)' : 'var(--text-dim)',
                fontSize: 12,
                padding: '5px 8px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <Icon name="folder" size={14} />
              {workspaceFiles.length > 0 && <span style={{ fontSize: 10, background: 'var(--accent)', color: 'white', padding: '1px 5px', borderRadius: 'var(--radius-full)', fontWeight: 700 }}>{workspaceFiles.length}</span>}
            </button>

            {/* Settings */}
            <button
              onClick={() => setSettingsOpen(!settingsOpen)}
              title="Settings"
              className="db-btn db-focus"
              style={{
                background: settingsOpen ? 'rgba(99,102,241,0.08)' : 'transparent',
                border: settingsOpen ? '1px solid rgba(99,102,241,0.2)' : '1px solid transparent',
                borderRadius: 'var(--radius-md)',
                color: settingsOpen ? 'var(--accent-hover)' : 'var(--text-dim)',
                fontSize: 12,
                padding: '5px 8px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <Icon name="settings" size={14} />
            </button>
          </div>
        </div>

        {/* Context bar — only shown when a GitHub repo is active */}
        {activeRepo && (
          <ContextBar
            project={activeRepo.name}
            branch={(activeRepo as any).default_branch || 'main'}
            lastTopic={active?.title && active.title !== 'New conversation' ? active.title : undefined}
          />
        )}

        {/* Chat area */}
        <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '24px 0' }}>
            {messages.length === 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 20, padding: '40px 24px' }}>
                {/* Welcome */}
                <div style={{ textAlign: 'center', maxWidth: 480 }}>
                  <div style={{ fontSize: 32, fontWeight: 800, letterSpacing: '-1px', background: 'linear-gradient(135deg, var(--text), var(--accent-hover))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', marginBottom: 8 }}>DevBuddy</div>
                  <p style={{ color: 'var(--text-dim)', fontSize: 15, lineHeight: 1.6 }}>Your AI engineering co-pilot. Build, debug, and ship faster.</p>
                </div>

                {/* Quick actions grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10, maxWidth: 480, width: '100%' }}>
                  {[
                    { label: 'Build a REST API', icon: 'zap', desc: 'FastAPI + PostgreSQL' },
                    { label: 'React Dashboard', icon: 'brain', desc: 'Charts + auth' },
                    { label: 'CI/CD Pipeline', icon: 'rocket', desc: 'GitHub Actions' },
                    { label: 'Debug Python', icon: 'wrench', desc: 'Trace + fix' },
                  ].map(s => (
                    <button key={s.label} onClick={() => setInput(s.label)} className="db-btn db-focus" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '16px', textAlign: 'left', cursor: 'pointer', transition: 'all var(--transition-base)' }} onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(99,102,241,0.4)'; e.currentTarget.style.background = 'rgba(99,102,241,0.06)'; e.currentTarget.style.transform = 'translateY(-1px)'; }} onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'var(--bg-card)'; e.currentTarget.style.transform = 'translateY(0)'; }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                        <Icon name={s.icon as any} size={16} style={{ color: 'var(--accent-hover)' }} />
                        <span style={{ color: 'var(--text)', fontSize: 13, fontWeight: 600 }}>{s.label}</span>
                      </div>
                      <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>{s.desc}</span>
                    </button>
                  ))}
                </div>

                {/* Tips row */}
                <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', justifyContent: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-faint)', fontSize: 12 }}>
                    <Icon name="command" size={12} /> <span>⌘K for commands</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-faint)', fontSize: 12 }}>
                    <Icon name="send" size={12} /> <span>Enter to send</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-faint)', fontSize: 12 }}>
                    <Icon name="folder" size={12} /> <span>Drop files anywhere</span>
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ maxWidth: 780, margin: '0 auto', padding: '0 20px' }}>
                {(() => {
                  // Group messages: user + its agent response into pairs for TaskCard rendering
                  const pairs: Array<{ user: Message; agent: Message | null }> = []
                  let i = 0
                  const msgs = messages
                  while (i < msgs.length) {
                    const m = msgs[i]
                    if (m.role === 'user') {
                      const next = msgs[i + 1]
                      if (next && next.role === 'assistant' && next.taskCard) {
                        // GitHub agent pair → render as one TaskCard
                        pairs.push({ user: m, agent: next })
                        i += 2
                      } else if (next && next.role === 'assistant' && !next.taskCard) {
                        // Regular chat pair
                        pairs.push({ user: m, agent: next })
                        i += 2
                      } else {
                        pairs.push({ user: m, agent: null })
                        i += 1
                      }
                    } else {
                      // Orphan assistant message
                      pairs.push({ user: { id: '_', role: 'user', content: '', ts: 0 }, agent: m })
                      i += 1
                    }
                  }

                  return pairs.map(({ user: uMsg, agent: aMsg }) => {
                    // ── TaskCard (GitHub agent) ──
                    if (aMsg?.taskCard) {
                      return (
                        <TaskCard
                          key={aMsg.id}
                          card={aMsg.taskCard}
                          userAvatar={user?.picture}
                          userName={user?.name}
                          isStreaming={aMsg.taskCard.status === 'running'}
                        />
                      )
                    }

                    // ── Regular chat bubble pair ──
                    return (
                      <div key={uMsg.id + (aMsg?.id ?? '')} style={{ marginBottom: 24 }}>
                        {/* User bubble */}
                        {uMsg.content && (
                          <div style={{ display: 'flex', gap: 12, flexDirection: 'row-reverse', marginBottom: 12 }}>
                            <div style={{ width: 32, height: 32, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(99,102,241,0.2)', border: '2px solid rgba(99,102,241,0.15)', overflow: 'hidden' }}>
                              {user?.picture ? <img src={user.picture} alt={user.name || 'User'} style={{ width: 32, height: 32, borderRadius: '50%' }} /> : <Icon name="user" size={16} style={{ color: '#818cf8' }} />}
                            </div>
                            <div className="message-enter" style={{ maxWidth: '78%', background: 'rgba(99,102,241,0.09)', border: '1px solid rgba(99,102,241,0.18)', borderRadius: '16px 16px 4px 16px', padding: '12px 16px' }}>
                              <div style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--text)', whiteSpace: 'pre-wrap' }}>{uMsg.content}</div>
                              <div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 4, textAlign: 'right' }}>{new Date(uMsg.ts).toLocaleTimeString()}</div>
                            </div>
                          </div>
                        )}

                        {/* Assistant bubble */}
                        {aMsg && (
                          <div style={{ display: 'flex', gap: 12 }}>
                            <div style={{ width: 32, height: 32, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(52,211,153,0.15)', border: '2px solid rgba(52,211,153,0.2)' }}>
                              <Icon name="bot" size={15} style={{ color: '#34d399' }} />
                            </div>
                            <div className="message-enter" style={{ maxWidth: '78%', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '4px 16px 16px 16px', padding: '14px 18px', boxShadow: '0 2px 12px rgba(0,0,0,0.1)' }}>
                              {aMsg.steps && aMsg.steps.length > 0 && (
                                <div style={{ marginBottom: 10, paddingBottom: 10, borderBottom: '1px solid var(--border-subtle)' }}>
                                  {aMsg.steps.filter(Boolean).map((step, si) => (
                                    <div key={si} style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 3, display: 'flex', alignItems: 'center', gap: 6 }}>
                                      <span style={{ color: 'var(--accent)' }}>→</span> {step}
                                    </div>
                                  ))}
                                </div>
                              )}
                              <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                components={{
                                  code: CodeBlock,
                                  pre: ({ children }) => <>{children}</>,
                                  p: ({ children }) => <p style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--text)', marginBottom: 8, marginTop: 0 }}>{children}</p>,
                                  ul: ({ children }) => <ul style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--text)', paddingLeft: 20, marginBottom: 8 }}>{children}</ul>,
                                  ol: ({ children }) => <ol style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--text)', paddingLeft: 20, marginBottom: 8 }}>{children}</ol>,
                                  li: ({ children }) => <li style={{ marginBottom: 4 }}>{children}</li>,
                                  strong: ({ children }) => <strong style={{ color: 'var(--accent-hover)', fontWeight: 600 }}>{children}</strong>,
                                  em: ({ children }) => <em style={{ color: 'var(--accent-hover)' }}>{children}</em>,
                                  a: ({ children, href }) => <a href={href} style={{ color: 'var(--accent-hover)', textDecoration: 'underline' }} target="_blank" rel="noopener noreferrer">{children}</a>,
                                }}
                              >
                                {aMsg.content}
                              </ReactMarkdown>
                              {aMsg.files && aMsg.files.length > 0 && (
                                <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
                                  <button onClick={() => downloadFiles(aMsg.files!)} style={{ background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.3)', borderRadius: 'var(--radius-sm)', color: 'var(--accent-hover)', fontSize: 12, fontWeight: 600, cursor: 'pointer', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <Icon name="download" size={12} /> Download {aMsg.files.length} file{aMsg.files.length > 1 ? 's' : ''} as ZIP
                                  </button>
                                </div>
                              )}
                              <div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 6 }}>{new Date(aMsg.ts).toLocaleTimeString()}</div>
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })
                })()}
                {loading && <TypingIndicator />}
                <div ref={bottomRef} />
                </div>
              )}
            </div>
        </div>

        {/* Settings modal — centered overlay */}
        {settingsOpen && (
          <div
            onClick={() => setSettingsOpen(false)}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(6px)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, animation: 'fadeIn 0.15s ease' }}
          >
          <div onClick={e => e.stopPropagation()} style={{
            width: '100%',
            maxWidth: 440,
            maxHeight: '85vh',
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-xl)',
            boxShadow: '0 24px 64px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            animation: 'modalContent 0.2s ease',
          }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
              <h2 style={{ margin: 0, fontSize: 15, color: 'var(--text)', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Icon name="settings" size={16} /> API Keys
              </h2>
              <button onClick={() => setSettingsOpen(false)} className="db-btn" style={{ background: 'none', border: 'none', color: 'var(--text-faint)', cursor: 'pointer', padding: '4px 6px', borderRadius: 'var(--radius-sm)', transition: 'all var(--transition-fast)' }} onMouseEnter={e => { e.currentTarget.style.color = 'var(--text)'; e.currentTarget.style.background = 'rgba(255,255,255,0.06)' }} onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-faint)'; e.currentTarget.style.background = 'none' }}><Icon name="close" size={16} /></button>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
              <p style={{ margin: '0 0 20px', fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.5 }}>
                Add your API keys to unlock LLM providers. Keys are encrypted at rest.
              </p>

              {[
                { id: 'anthropic', name: 'Anthropic', icon: 'brain', placeholder: 'sk-ant-api03-...', defaultUrl: 'https://api.anthropic.com' },
                { id: 'ollama', name: 'Ollama', icon: 'bot', placeholder: 'Ollama API key (if required)', defaultUrl: 'https://ollama.com' },
                { id: 'llama', name: 'Llama API', icon: 'zap', placeholder: 'Bearer token...', defaultUrl: 'https://api.llama.com/v1' },
              ].map(provider => (
                <div key={provider.id} style={{ marginBottom: 20, padding: 16, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                    <Icon name={provider.icon as any} size={18} style={{ color: 'var(--accent-hover)' }} />
                    <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--accent-hover)' }}>{provider.name}</span>
                    {providerKeys[provider.id as keyof typeof providerKeys].key === '••••••••' && (
                      <span style={{ fontSize: 11, color: 'var(--success)', background: 'rgba(16,185,129,0.1)', padding: '2px 8px', borderRadius: 'var(--radius-sm)' }}>Configured</span>
                    )}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div>
                      <label style={{ fontSize: 11, color: 'var(--text-faint)', marginBottom: 4, display: 'block' }}>API Key</label>
                      <input
                        type="password"
                        value={providerKeys[provider.id as keyof typeof providerKeys].key}
                        onChange={e => setProviderKeys(prev => ({ ...prev, [provider.id]: { ...prev[provider.id as keyof typeof prev], key: e.target.value } }))}
                        placeholder={provider.placeholder}
                        className="db-input"
                        style={{
                          width: '100%',
                          background: 'var(--bg-elevated)',
                          border: '1px solid var(--border)',
                          borderRadius: 'var(--radius-md)',
                          padding: '8px 12px',
                          color: 'var(--text)',
                          fontSize: 13,
                          outline: 'none',
                          fontFamily: 'monospace'
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: 11, color: 'var(--text-faint)', marginBottom: 4, display: 'block' }}>Base URL (optional)</label>
                      <input
                        type="text"
                        value={providerKeys[provider.id as keyof typeof providerKeys].base_url}
                        onChange={e => setProviderKeys(prev => ({ ...prev, [provider.id]: { ...prev[provider.id as keyof typeof prev], base_url: e.target.value } }))}
                        placeholder={provider.defaultUrl}
                        className="db-input"
                        style={{
                          width: '100%',
                          background: 'var(--bg-elevated)',
                          border: '1px solid var(--border)',
                          borderRadius: 'var(--radius-md)',
                          padding: '8px 12px',
                          color: 'var(--text)',
                          fontSize: 13,
                          outline: 'none',
                          fontFamily: 'monospace'
                        }}
                      />
                    </div>
                  </div>
                </div>
              ))}

              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 8, paddingTop: 4 }}>
                <button
                  onClick={() => setSettingsOpen(false)}
                  className="db-btn db-focus"
                  style={{
                    padding: '8px 16px',
                    background: 'transparent',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--text-muted)',
                    fontSize: 13,
                    cursor: 'pointer',
                    transition: 'all var(--transition-base)'
                  }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--text-faint)'; e.currentTarget.style.color = 'var(--accent-hover)'; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-muted)'; }}
                >
                  Cancel
                </button>
                <button
                  onClick={saveProviderKeys}
                  disabled={savingKeys}
                  className="db-btn db-focus"
                  style={{
                    padding: '8px 20px',
                    background: 'linear-gradient(135deg, var(--accent), var(--accent-hover))',
                    border: 'none',
                    borderRadius: 'var(--radius-md)',
                    color: 'white',
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: savingKeys ? 'not-allowed' : 'pointer',
                    opacity: savingKeys ? 0.7 : 1,
                    transition: 'all var(--transition-base)',
                    boxShadow: '0 2px 12px rgba(99,102,241,0.3)'
                  }}
                  onMouseEnter={e => { if (!savingKeys) { e.currentTarget.style.boxShadow = '0 4px 16px rgba(99,102,241,0.4)'; e.currentTarget.style.transform = 'translateY(-1px)' }}}
                  onMouseLeave={e => { e.currentTarget.style.boxShadow = '0 2px 12px rgba(99,102,241,0.3)'; e.currentTarget.style.transform = 'translateY(0)' }}
                >
                  {savingKeys ? 'Saving...' : 'Save Keys'}
                </button>
              </div>
            </div>
          </div>
          </div>
        )}

        {/* Input area */}
        <div style={{ padding: '16px 20px 20px', borderTop: '1px solid var(--border-subtle)', flexShrink: 0 }}>
          <div style={{ maxWidth: 760, margin: '0 auto' }}>
            {/* Main input container */}
            <div
              style={{ position: 'relative', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-xl)', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8, boxShadow: '0 4px 24px rgba(0,0,0,0.2)', transition: 'border-color var(--transition-base), box-shadow var(--transition-base)' }}
              className="db-input-container"
              id="chat-input-container"
              onDragOver={e => { e.preventDefault(); const el = document.getElementById('chat-input-container'); if (el) el.style.borderColor = 'var(--accent)'; }}
              onDragLeave={e => { e.preventDefault(); const el = document.getElementById('chat-input-container'); if (el) el.style.borderColor = 'var(--border)'; }}
              onDrop={e => {
                e.preventDefault()
                const el = document.getElementById('chat-input-container')
                if (el) el.style.borderColor = 'var(--border)'
                const files = Array.from(e.dataTransfer.files)
                if (files.length > 0) {
                  const fileNames = files.map(f => f.name).join(', ')
                  setInput(prev => prev + (prev ? '\n\n' : '') + `[Attached: ${fileNames}]`)
                }
              }}
            >
              {/* Textarea */}
              <textarea
                ref={textareaRef}
                value={input}
                onChange={handleInputChange}
                onKeyDown={onKeyDown}
                placeholder={activeRepo && agentMode ? `Describe a task for ${activeRepo.name}… (runs in isolated GitHub Actions runner)` : "Describe what you want to build, or type @ to reference files..."}
                rows={1}
                className="db-input"
                style={{ width: '100%', background: 'none', border: 'none', outline: 'none', color: 'var(--text)', fontSize: 14, lineHeight: 1.5, resize: 'none', maxHeight: 200, fontFamily: 'inherit', overflowY: 'auto', padding: '0 4px' }}
                onFocus={e => { const container = document.getElementById('chat-input-container'); if (container) { container.style.borderColor = 'rgba(99,102,241,0.4)'; container.style.boxShadow = '0 4px 24px rgba(0,0,0,0.2), 0 0 0 3px rgba(99,102,241,0.1)'; } }}
                onBlur={e => { setTimeout(() => setMentionOpen(false), 200); const container = document.getElementById('chat-input-container'); if (container) { container.style.borderColor = 'var(--border)'; container.style.boxShadow = '0 4px 24px rgba(0,0,0,0.2)'; } }}
              />

              {/* @mention dropdown */}
              {mentionOpen && filteredMentions.length > 0 && (
                <div style={{
                  position: 'absolute',
                  bottom: '100%',
                  left: 0,
                  right: 0,
                  marginBottom: 8,
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-lg)',
                  boxShadow: 'var(--shadow-lg), 0 0 0 1px rgba(99,102,241,0.1)',
                  maxHeight: 200,
                  overflowY: 'auto',
                  zIndex: 50,
                  animation: 'dropdownIn 0.15s ease',
                }}>
                  <div style={{ padding: '8px 12px', fontSize: 11, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.5px', borderBottom: '1px solid var(--border-subtle)' }}>
                    <Icon name="folder" size={10} /> Project Files
                  </div>
                  {filteredMentions.map((f, i) => (
                    <button
                      key={f}
                      onMouseDown={e => {
                        e.preventDefault()
                        const lastAt = input.lastIndexOf('@')
                        if (lastAt >= 0) {
                          const before = input.slice(0, lastAt)
                          const after = input.slice(lastAt + 1 + mentionQuery.length)
                          setInput(before + '@' + f + ' ' + after)
                          setMentionOpen(false)
                          setMentionQuery('')
                        }
                      }}
                      className="db-btn"
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        textAlign: 'left',
                        background: i === mentionIndex ? 'rgba(99,102,241,0.1)' : 'transparent',
                        border: 'none',
                        borderBottom: '1px solid var(--border-subtle)',
                        color: i === mentionIndex ? 'var(--accent-hover)' : 'var(--text-muted)',
                        fontSize: 13,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        transition: 'all var(--transition-fast)',
                      }}
                      onMouseEnter={e => { setMentionIndex(i); e.currentTarget.style.background = 'rgba(99,102,241,0.1)'; e.currentTarget.style.color = 'var(--accent-hover)' }}
                      onMouseLeave={e => { e.currentTarget.style.background = i === mentionIndex ? 'rgba(99,102,241,0.1)' : 'transparent'; e.currentTarget.style.color = i === mentionIndex ? 'var(--accent-hover)' : 'var(--text-muted)' }}
                    >
                      <Icon name="file" size={14} style={{ color: 'var(--text-faint)' }} />
                      <span>{f}</span>
                    </button>
                  ))}
                </div>
              )}

              {/* Bottom toolbar */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                {/* Left: mode indicator */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <button
                    onClick={() => setAgentMode(!agentMode)}
                    title={agentMode ? 'Agent Mode — full autonomous pipeline' : 'Chat Mode — raw LLM'}
                    className="db-btn db-focus"
                    style={{
                      background: agentMode ? 'rgba(16,185,129,0.1)' : 'transparent',
                      border: agentMode ? '1px solid rgba(16,185,129,0.2)' : '1px solid transparent',
                      borderRadius: 'var(--radius-full)',
                      color: agentMode ? 'var(--success)' : 'var(--text-dim)',
                      fontSize: 11,
                      fontWeight: 600,
                      padding: '4px 10px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                      transition: 'all var(--transition-base)'
                    }}
                  >
                    <Icon name={agentMode ? 'agent' : 'chat'} size={12} />
                    {agentMode ? 'Agent' : 'Chat'}
                  </button>

                </div>

                {/* Right: model selector + send */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Dropdown
                    value={model}
                    options={models.map(m => ({ value: m.id, label: m.label, description: m.provider }))}
                    onChange={setModel}
                    disabled={modelsLoading}
                  />

                  <button
                    onClick={loading ? cancelRequest : send}
                    disabled={!input.trim() && !loading}
                    title={loading ? 'Cancel' : 'Send'}
                    className="db-btn db-focus"
                    style={{
                      width: 34,
                      height: 34,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: loading ? 'rgba(239,68,68,0.15)' : input.trim() ? 'linear-gradient(135deg, var(--accent), var(--accent-hover))' : 'var(--border)',
                      border: loading ? '1px solid rgba(239,68,68,0.3)' : 'none',
                      borderRadius: '50%',
                      color: loading ? 'var(--error)' : input.trim() ? 'white' : 'var(--text-faint)',
                      fontSize: 16,
                      fontWeight: 600,
                      cursor: input.trim() || loading ? 'pointer' : 'not-allowed',
                      flexShrink: 0,
                      transition: 'all var(--transition-base)',
                      boxShadow: input.trim() && !loading ? '0 2px 12px rgba(99,102,241,0.3)' : 'none'
                    }}
                    onMouseEnter={e => { if (input.trim() && !loading) { e.currentTarget.style.boxShadow = '0 4px 16px rgba(99,102,241,0.4)'; e.currentTarget.style.transform = 'translateY(-1px) scale(1.05)' }}}
                    onMouseLeave={e => { if (input.trim() && !loading) { e.currentTarget.style.boxShadow = '0 2px 12px rgba(99,102,241,0.3)'; e.currentTarget.style.transform = 'translateY(0) scale(1)' }}}
                  >
                    {loading ? <Icon name="close" size={14} /> : <Icon name="send" size={14} />}
                  </button>
                </div>
              </div>
            </div>

            {/* Hint text — only on desktop */}
            {!isMobile && (
              <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, fontSize: 11, color: 'var(--text-faint)', opacity: 0.7 }}>
                <span>↵ send · ⇧↵ newline · {navigator.platform.includes('Mac') ? '⌘' : 'Ctrl'}K commands</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* GitHub Panel */}
      <GitHubPanelWrapper
        token={localStorage.getItem('devbuddy_token') || ''}
        isOpen={githubPanelOpen}
        onClose={() => setGithubPanelOpen(false)}
        onSelectRepo={repo => { setActiveRepoLocal(repo); toast(`Working in ${repo.full_name}`, 'success') }}
      />

      {/* Workspace panel */}
      {workspaceOpen && (
        <WorkspacePanel
          files={workspaceFiles.map(path => {
            const fileData = messages.flatMap(m => m.files || []).find(f => f.name === path)
            return { name: path, content: fileData?.content }
          })}
          onDownload={(files) => downloadFiles(files.filter(f => f.content).map(f => ({ name: f.name, content: f.content! })))}
          onDownloadOne={(file) => file.content && downloadFiles([{ name: file.name, content: file.content }])}
          isOpen={workspaceOpen}
          onToggle={() => setWorkspaceOpen(!workspaceOpen)}
        />
      )}

      {/* Command palette */}
      <CommandPalette
        isOpen={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        commands={[
          { id: 'new-chat', label: 'New conversation', shortcut: 'Ctrl+N', icon: 'sparkles', action: () => { createNew(); setWorkspaceOpen(false) } },
          { id: 'workspace', label: 'Toggle workspace panel', shortcut: 'Ctrl+Shift+F', icon: 'folder', action: () => setWorkspaceOpen(!workspaceOpen) },
          { id: 'settings', label: 'Open settings', shortcut: '', icon: 'settings', action: () => setSettingsOpen(true) },
          { id: 'agent-mode', label: agentMode ? 'Switch to Chat mode' : 'Switch to Agent mode', shortcut: '', icon: agentMode ? 'chat' : 'agent', action: () => setAgentMode(!agentMode) },
          { id: 'logout', label: 'Sign out', shortcut: '', icon: 'logout', action: () => logout() },
        ]}
        conversations={convs.map(c => ({ id: c.id, title: c.title, messageCount: c.messages.length }))}
        onSelectConversation={(id) => { selectConv(id); setPaletteOpen(false) }}
      />

      <ToastContainer />
    </div>
  )
}

// ── GitHub helpers ─────────────────────────────────────────────────────────

function GitHubRepoButton({ activeRepo, onClick }: { activeRepo: { name: string; owner: string; html_url: string } | null; onClick: () => void }) {
  if (activeRepo) {
    return (
      <button
        onClick={onClick}
        className="db-btn db-focus"
        title="Change repository"
        style={{ background: 'rgba(36,41,46,0.6)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 'var(--radius-md)', color: 'var(--text-muted)', fontSize: 12, padding: '4px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, maxWidth: 180 }}
      >
        <Icon name="git" size={12} />
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{activeRepo.name}</span>
      </button>
    )
  }
  return (
    <button
      onClick={onClick}
      className="db-btn db-focus"
      title="Connect GitHub repository"
      style={{ background: 'transparent', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', color: 'var(--text-dim)', fontSize: 12, padding: '4px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
      onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.2)'; e.currentTarget.style.color = 'var(--text-muted)' }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-dim)' }}
    >
      <Icon name="git" size={12} /> GitHub
    </button>
  )
}

function GitHubPanelWrapper(props: { token: string; isOpen: boolean; onClose: () => void; onSelectRepo: (r: any) => void }) {
  return (
    <GitHubProvider token={props.token}>
      <GitHubPanel {...props} />
    </GitHubProvider>
  )
}
