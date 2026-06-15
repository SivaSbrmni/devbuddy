import { useState, useRef, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
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

interface Model {
  id: string
  label: string
  provider: string
  family: string
}

const FALLBACK_MODELS: Model[] = [
  { id: 'claude-3-5-sonnet', label: 'Claude 3.5 Sonnet', provider: 'anthropic', family: 'claude' }
]

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  ts: number
  steps?: string[]
  files?: { name: string; content: string }[]
  agentEvents?: AgentEvent[]
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

  const updateActive = (msgs: Message[], title?: string) => {
    const list = convs.map(c =>
      c.id === activeId
        ? { ...c, messages: msgs, title: title || c.title, ts: Date.now() }
        : c
    )
    save(list)
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
      if (providerKeys.anthropic.key && providerKeys.anthropic.key !== '••••••••') {
        payload.anthropic = providerKeys.anthropic
      }
      if (providerKeys.ollama.key && providerKeys.ollama.key !== '••••••••') {
        payload.ollama = providerKeys.ollama
      }
      if (providerKeys.llama.key && providerKeys.llama.key !== '••••••••') {
        payload.llama = providerKeys.llama
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
    const title = conv.messages.length === 0 ? text.slice(0, 50) : conv.title
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
      {sidebarOpen && (
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
            display: isMobile ? 'block' : 'none',
            animation: 'fadeIn 0.2s ease',
          }}
        />
      )}

      {/* ── Left dock (2050 OS: minimal, icon-based) ── */}
      <div style={{
        width: 56,
        background: 'var(--bg-elevated)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        alignItems: 'center',
        padding: '12px 0',
        gap: 4,
        position: isMobile ? 'fixed' : 'relative',
        left: isMobile ? (sidebarOpen ? 0 : -56) : 0,
        top: 0,
        bottom: 0,
        zIndex: 50,
        transition: 'left 0.3s ease',
      }}>
        {/* App icon */}
        <div style={{
          width: 32,
          height: 32,
          borderRadius: 'var(--radius-md)',
          background: 'linear-gradient(135deg, var(--accent), var(--accent-hover))',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 16,
          boxShadow: '0 4px 12px rgba(99,102,241,0.3)',
        }}>
          <Icon name="sparkles" size={18} style={{ color: 'white' }} />
        </div>

        {/* New conversation */}
        <button
          onClick={createNew}
          title="New conversation (Ctrl+N)"
          className="db-btn"
          style={{
            width: 40,
            height: 40,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 'var(--radius-md)',
            background: 'transparent',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            transition: 'all var(--transition-fast)',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(99,102,241,0.1)'; e.currentTarget.style.color = 'var(--accent-hover)' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-muted)' }}
        >
          <Icon name="plus" size={20} />
        </button>

        {/* Divider */}
        <div style={{ width: 24, height: 1, background: 'var(--border-subtle)', margin: '8px 0' }} />

        {/* Conversation dots — color-coded for visual memory */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'center', flex: 1, overflow: 'hidden', padding: '4px 0' }}>
          {convs.slice(0, 6).map(c => {
            const hue = c.title.split('').reduce((acc, ch) => acc + ch.charCodeAt(0), 0) % 360
            const isActive = c.id === activeId
            return (
              <button
                key={c.id}
                onClick={() => selectConv(c.id)}
                title={c.title}
                className="db-btn"
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  background: isActive ? `hsl(${hue}, 70%, 55%)` : `hsl(${hue}, 50%, 20%)`,
                  border: isActive ? `2px solid hsl(${hue}, 70%, 65%)` : '1px solid var(--border)',
                  color: 'white',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 11,
                  fontWeight: 700,
                  transition: 'all var(--transition-fast)',
                  flexShrink: 0,
                  boxShadow: isActive ? `0 0 0 2px hsl(${hue}, 70%, 55%, 0.3)` : 'none',
                }}
              >
                {c.title.charAt(0).toUpperCase()}
              </button>
            )
          })}
          {convs.length > 6 && (
            <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>+{convs.length - 6}</span>
          )}
        </div>

        {/* Bottom actions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'center', marginTop: 'auto' }}>
          <button
            onClick={() => setPaletteOpen(true)}
            title="Command palette (Cmd+K)"
            className="db-btn"
            style={{
              width: 40,
              height: 40,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 'var(--radius-md)',
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              transition: 'all var(--transition-fast)',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.color = 'var(--text)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-muted)' }}
          >
            <Icon name="command" size={18} />
          </button>

          {user?.picture ? (
            <img
              src={user.picture}
              alt={`${user?.name || 'User'} avatar`}
              onClick={logout}
              title="Sign out"
              style={{
                width: 32,
                height: 32,
                borderRadius: '50%',
                objectFit: 'cover',
                border: '2px solid var(--border)',
                cursor: 'pointer',
                transition: 'all var(--transition-fast)',
              }}
            />
          ) : (
            <button
              onClick={logout}
              title="Sign out"
              className="db-btn"
              style={{
                width: 32,
                height: 32,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: '50%',
                background: 'var(--bg-card)',
                border: '1px solid var(--border)',
                color: 'var(--text-muted)',
                cursor: 'pointer',
              }}
            >
              <Icon name="logout" size={14} />
            </button>
          )}
        </div>
      </div>

      {/* ── Main chat area ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

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
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                minWidth: 160,
                justifyContent: 'flex-start',
              }}
            >
              <Icon name="command" size={12} />
              <span style={{ fontSize: 12 }}>Search or command...</span>
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

        {/* Context bar — project awareness */}
        <ContextBar
          project="devbuddy"
          branch="main"
          files={[
            { path: 'frontend/src/App.tsx', status: 'modified' },
            { path: 'frontend/src/pages/Workspace.tsx', status: 'modified' },
            { path: 'frontend/src/components/ContextBar.tsx', status: 'new' },
            { path: 'backend/app/main.py', status: 'clean' },
          ]}
          lastTopic={active?.title && active.title !== 'New conversation' ? active.title : undefined}
        />

        {/* Chat area */}
        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div style={{ flex: 1, overflowY: 'auto', padding: '24px 0' }}>
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
                    <button key={s.label} onClick={() => { setInput(s.label); setTimeout(() => send(), 50) }} className="db-btn db-focus" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '16px', textAlign: 'left', cursor: 'pointer', transition: 'all var(--transition-base)' }} onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(99,102,241,0.4)'; e.currentTarget.style.background = 'rgba(99,102,241,0.06)'; e.currentTarget.style.transform = 'translateY(-1px)'; }} onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'var(--bg-card)'; e.currentTarget.style.transform = 'translateY(0)'; }}>
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
              <div style={{ maxWidth: 760, margin: '0 auto', padding: '0 20px' }}>
                  {messages.map(msg => (
                    <div key={msg.id} style={{ marginBottom: 24, display: 'flex', gap: 12, flexDirection: msg.role === 'user' ? 'row-reverse' : 'row' }}>
                      <div style={{ width: 32, height: 32, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 700, background: msg.role === 'user' ? 'rgba(99,102,241,0.2)' : 'rgba(16,185,129,0.15)', color: msg.role === 'user' ? 'var(--accent-hover)' : 'var(--success)', border: `2px solid ${msg.role === 'user' ? 'rgba(99,102,241,0.15)' : 'rgba(16,185,129,0.1)'}` }}>
                        {msg.role === 'user' ? (user?.picture ? <img src={user.picture} alt={`${user?.name || 'User'} avatar`} style={{ width: 32, height: 32, borderRadius: '50%' }} /> : <Icon name="user" size={16} />) : <Icon name="bot" size={16} />}
                      </div>
                      <div className="message-enter" style={{ maxWidth: '80%', background: msg.role === 'user' ? 'rgba(99,102,241,0.1)' : 'var(--bg-card)', border: `1px solid ${msg.role === 'user' ? 'rgba(99,102,241,0.2)' : 'var(--border)'}`, borderRadius: 'var(--radius-lg)', padding: '14px 18px', boxShadow: msg.role === 'user' ? '0 2px 8px rgba(99,102,241,0.08)' : '0 2px 8px rgba(0,0,0,0.1)' }}>
                        {msg.steps && msg.steps.length > 0 && (
                          <div style={{ marginBottom: 12, paddingBottom: 12, borderBottom: '1px solid var(--border)' }}>
                            <div style={{ fontSize: 11, color: 'var(--accent)', fontWeight: 600, marginBottom: 6 }}>
                              {msg.agentEvents && msg.agentEvents.length > 0 ? <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}><Icon name="agent" size={12} /> Agent pipeline</span> : <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}><Icon name="loader" size={12} /> Working...</span>}
                            </div>
                            {msg.steps.filter(s => s).map((step, i) => (
                              <div key={i} style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                                <span style={{ color: 'var(--accent)' }}>→</span> {step}
                              </div>
                            ))}
                            {msg.agentEvents && msg.agentEvents.some(e => e.type === 'test') && (
                              <div style={{ marginTop: 8, padding: '6px 10px', background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', borderRadius: 'var(--radius-sm)' }}>
                                {msg.agentEvents.filter(e => e.type === 'test').map((e, i) => (
                                  <div key={i} style={{ fontSize: 11, color: 'var(--success)' }}>
                                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Icon name="check" size={10} /> {e.payload?.summary || 'Tests passed'}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                            {msg.agentEvents && msg.agentEvents.some(e => e.type === 'review') && (
                              <div style={{ marginTop: 8, padding: '6px 10px', background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 'var(--radius-sm)' }}>
                                {msg.agentEvents.filter(e => e.type === 'review').map((e, i) => (
                                  <div key={i} style={{ fontSize: 11, color: 'var(--accent-hover)' }}>
                                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Icon name="info" size={10} /> {e.payload?.summary || 'Code reviewed'}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                        {msg.role === 'assistant' ? (
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              code: CodeBlock,
                              pre: ({ children }) => <>{children}</>,
                              p: ({ children }) => <p style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--text)', marginBottom: 8 }}>{children}</p>,
                              ul: ({ children }) => <ul style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--text)', paddingLeft: 20, marginBottom: 8 }}>{children}</ul>,
                              ol: ({ children }) => <ol style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--text)', paddingLeft: 20, marginBottom: 8 }}>{children}</ol>,
                              li: ({ children }) => <li style={{ marginBottom: 4 }}>{children}</li>,
                              strong: ({ children }) => <strong style={{ color: 'var(--accent-hover)', fontWeight: 600 }}>{children}</strong>,
                              em: ({ children }) => <em style={{ color: 'var(--accent-hover)' }}>{children}</em>,
                              a: ({ children, href }) => <a href={href} style={{ color: 'var(--accent-hover)', textDecoration: 'underline' }} target="_blank" rel="noopener noreferrer">{children}</a>,
                            }}
                          >
                            {msg.content}
                          </ReactMarkdown>
                        ) : (
                          <div style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--text)', whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                        )}
                        {msg.files && msg.files.length > 0 && (
                          <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
                            <button
                              onClick={() => downloadFiles(msg.files!)}
                              style={{
                                background: 'rgba(99,102,241,0.12)',
                                border: '1px solid rgba(99,102,241,0.3)',
                                borderRadius: 'var(--radius-sm)',
                                color: 'var(--accent-hover)',
                                fontSize: 12,
                                fontWeight: 600,
                                cursor: 'pointer',
                                padding: '6px 12px',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6
                              }}
                            >
                              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}><Icon name="download" size={12} /> Download {msg.files.length} file{msg.files.length > 1 ? 's' : ''} as ZIP</span>
                            </button>
                            <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-faint)' }}>
                              {msg.files.map(f => f.name).join(', ')}
                            </div>
                          </div>
                        )}
                        <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 6 }}>{new Date(msg.ts).toLocaleTimeString()}</div>
                      </div>
                    </div>
                  ))}
                  {loading && (
                    <TypingIndicator />
                  )}
                  <div ref={bottomRef} />
                </div>
              )}
            </div>
        </div>

        {/* Settings panel — right side, no modal */}
        {settingsOpen && (
          <div style={{
            width: 340,
            background: 'var(--bg-elevated)',
            borderLeft: '1px solid var(--border-subtle)',
            display: 'flex',
            flexDirection: 'column',
            flexShrink: 0,
            overflow: 'hidden',
            animation: 'slideInRight 0.2s ease',
          }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <h2 style={{ margin: 0, fontSize: 15, color: 'var(--text)', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Icon name="settings" size={16} /> API Keys
              </h2>
              <button onClick={() => setSettingsOpen(false)} className="db-btn" style={{ background: 'none', border: 'none', color: 'var(--text-faint)', cursor: 'pointer', fontSize: 18, padding: '2px 6px', borderRadius: 'var(--radius-sm)', transition: 'all var(--transition-fast)' }} onMouseEnter={e => { e.currentTarget.style.color = 'var(--text)' }} onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-faint)' }}><Icon name="close" size={16} /></button>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
              <p style={{ margin: '0 0 20px', fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.5 }}>
                Add your API keys to unlock LLM providers. Keys are encrypted at rest. You can also override the default API base URL for each provider.
              </p>

              {[
                { id: 'anthropic', name: 'Anthropic', icon: 'brain', placeholder: 'sk-ant-api03-...', defaultUrl: 'https://api.anthropic.com' },
                { id: 'ollama', name: 'Ollama', icon: 'bot', placeholder: 'Optional — leave empty for local', defaultUrl: 'http://localhost:11434' },
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

              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 8 }}>
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
                placeholder="Describe what you want to build, or type @ to reference files..."
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

            {/* Hint text */}
            <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, fontSize: 11, color: 'var(--text-faint)' }}>
              <span>Enter to send · Shift+Enter for new line · {navigator.platform.includes('Mac') ? 'Cmd' : 'Ctrl'}+K for commands</span>
            </div>
          </div>
        </div>
      </div>

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
