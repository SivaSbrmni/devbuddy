import { useState, useRef, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import JSZip from 'jszip'

const BACKEND = import.meta.env.VITE_API_URL || ''
const API = `${BACKEND}/api/v1`

interface Model {
  id: string
  label: string
  provider: string
  family: string
}

const FALLBACK_MODELS: Model[] = [
  { id: 'claude-sonnet-4', label: 'Claude Sonnet 4', provider: 'anthropic', family: 'anthropic' },
  { id: 'qwen3-coder:480b', label: 'Qwen3 Coder', provider: 'ollama', family: 'ollama' },
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

  return { convs, active, activeId, createNew, updateActive, selectConv, deleteConv }
}

export default function ChatPage() {
  const { user, logout } = useAuth()
  const { convs, active, activeId, createNew, updateActive, selectConv, deleteConv } = useConversations()
  const [models, setModels] = useState<Model[]>(FALLBACK_MODELS)
  const [modelsLoading, setModelsLoading] = useState(true)
  const [model, setModel] = useState(FALLBACK_MODELS[0].id)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [knowledgeOpen, setKnowledgeOpen] = useState(false)
  const [mcpOpen, setMcpOpen] = useState(false)
  const [knowledgeQuery, setKnowledgeQuery] = useState('')
  const [knowledgeResults, setKnowledgeResults] = useState<any[]>([])
  const [mcpTools, setMcpTools] = useState<any[]>([])
  const [activeTab, setActiveTab] = useState<'activity' | 'llm' | 'mcps' | 'files'>('activity')
  const [agentMode, setAgentMode] = useState(false)
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [workspaceFiles, setWorkspaceFiles] = useState<string[]>([])
  const abortControllerRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const messages = active?.messages || []

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (!activeId && !loading) createNew()
  }, [])

  // Fetch models on mount
  useEffect(() => {
    const fetchModels = async () => {
      try {
        setModelsLoading(true)
        const resp = await fetch(`${API}/models`)
        if (resp.ok) {
          const data = await resp.json()
          setModels(data)
          if (data.length > 0 && !models.find(m => m.id === model)) {
            setModel(data[0].id)
          }
        }
      } catch (e) {
        console.error('Failed to fetch models:', e)
      } finally {
        setModelsLoading(false)
      }
    }
    fetchModels()
  }, [])

  // Fetch MCP tools on mount
  useEffect(() => {
    const fetchMcpTools = async () => {
      try {
        const resp = await fetch(`${API}/mcp/tools`)
        if (resp.ok) {
          const data = await resp.json()
          setMcpTools(data)
        }
      } catch (e) {
        console.error('Failed to fetch MCP tools:', e)
      }
    }
    fetchMcpTools()
  }, [])

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

  const send = async () => {
    const text = input.trim()
    if (!text || loading) return

    let conv = active
    if (!conv) conv = createNew()

    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', content: text, ts: Date.now() }
    const title = conv.messages.length === 0 ? text.slice(0, 50) : conv.title
    const newMsgs = [...conv.messages, userMsg]
    updateActive(newMsgs, title)
    setInput('')
    setLoading(true)
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
  }

  const searchKnowledge = async () => {
    if (!knowledgeQuery.trim()) return
    try {
      const resp = await fetch(`${API}/knowledge/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: knowledgeQuery, limit: 10 })
      })
      if (resp.ok) {
        const data = await resp.json()
        setKnowledgeResults(data)
      }
    } catch (e) {
      console.error('Failed to search knowledge:', e)
    }
  }

  const callMcpTool = async (serverId: string, toolName: string, args: any) => {
    try {
      const resp = await fetch(`${API}/mcp/tools/call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          server_id: serverId,
          tool_name: toolName,
          arguments: args
        })
      })
      if (resp.ok) {
        const data = await resp.json()
        return data
      }
    } catch (e) {
      console.error('Failed to call MCP tool:', e)
      return { success: false, error: String(e) }
    }
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
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
    return (
      <div style={{ position: 'relative', marginTop: 8, marginBottom: 8 }}>
        <div style={{
          position: 'absolute',
          top: 0,
          right: 0,
          background: '#2a2d3a',
          color: '#9ca3af',
          fontSize: 11,
          padding: '4px 8px',
          borderRadius: '0 4px 0 4px',
          fontFamily: 'monospace'
        }}>
          {language}
        </div>
        <pre style={{
          background: '#1a1d27',
          border: '1px solid #2a2d3a',
          borderRadius: 8,
          padding: '12px',
          overflowX: 'auto',
          fontSize: 13,
          lineHeight: 1.5,
          color: '#e4e6eb'
        }}>
          <code className={className} {...props}>{children}</code>
        </pre>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', height: '100vh', background: '#0d0f14', color: '#e4e6eb', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' }}>

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
            background: 'rgba(0,0,0,0.5)',
            zIndex: 40,
            display: window.innerWidth < 768 ? 'block' : 'none'
          }}
        />
      )}

      {/* ── Left sidebar ── */}
      <div style={{
        width: 260,
        background: '#111318',
        borderRight: '1px solid #1e2130',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        position: window.innerWidth < 768 ? 'fixed' : 'relative',
        left: window.innerWidth < 768 ? (sidebarOpen ? 0 : -260) : 0,
        top: 0,
        bottom: 0,
        zIndex: 50,
        transition: 'left 0.3s ease'
      }}>
        {/* Logo */}
        <div style={{ padding: '18px 16px 12px', borderBottom: '1px solid #1e2130' }}>
          <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.5px', background: 'linear-gradient(135deg, #e4e6eb, #818cf8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>DevBuddy</div>
          <div style={{ fontSize: 11, color: '#4b4f63', marginTop: 2 }}>AI Engineering Co-pilot</div>
        </div>

        {/* New chat button */}
        <div style={{ padding: '10px 12px' }}>
          <button onClick={createNew} style={{ width: '100%', padding: '8px 12px', background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.3)', borderRadius: 8, color: '#818cf8', fontSize: 13, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 16 }}>+</span> New conversation
          </button>
        </div>

        {/* Conversation list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '0 8px' }}>
          {convs.length === 0 && (
            <div style={{ fontSize: 12, color: '#4b4f63', padding: '12px 8px' }}>No conversations yet</div>
          )}
          {convs.map(c => (
            <div key={c.id} onClick={() => selectConv(c.id)}
              style={{ padding: '8px 10px', borderRadius: 8, marginBottom: 2, cursor: 'pointer', background: c.id === activeId ? 'rgba(99,102,241,0.1)' : 'transparent', border: c.id === activeId ? '1px solid rgba(99,102,241,0.2)' : '1px solid transparent', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}
            >
              <div style={{ overflow: 'hidden' }}>
                <div style={{ fontSize: 13, color: c.id === activeId ? '#c7d2fe' : '#9ca3af', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.title}</div>
                <div style={{ fontSize: 11, color: '#4b4f63', marginTop: 2 }}>{c.messages.length} messages</div>
              </div>
              <button onClick={e => { e.stopPropagation(); deleteConv(c.id) }} style={{ background: 'none', border: 'none', color: '#4b4f63', cursor: 'pointer', fontSize: 14, padding: '0 2px', flexShrink: 0 }}>×</button>
            </div>
          ))}
        </div>

        {/* User info */}
        <div style={{ padding: '12px 16px', borderTop: '1px solid #1e2130', display: 'flex', alignItems: 'center', gap: 10 }}>
          {user?.picture && <img src={user.picture} alt="" style={{ width: 28, height: 28, borderRadius: '50%', objectFit: 'cover' }} />}
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <div style={{ fontSize: 13, color: '#e4e6eb', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user?.name}</div>
            <div style={{ fontSize: 11, color: '#4b4f63', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user?.email}</div>
          </div>
          <button onClick={logout} title="Sign out" style={{ background: 'none', border: 'none', color: '#4b4f63', cursor: 'pointer', fontSize: 16 }}>⏻</button>
        </div>

        {/* Close button for mobile */}
        {window.innerWidth < 768 && (
          <button
            onClick={() => setSidebarOpen(false)}
            style={{
              position: 'absolute',
              top: 12,
              right: 12,
              background: 'none',
              border: 'none',
              color: '#4b4f63',
              cursor: 'pointer',
              fontSize: 20,
              zIndex: 60
            }}
          >
            ×
          </button>
        )}
      </div>

      {/* ── Main chat area ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

        {/* Top bar */}
        <div style={{ padding: '12px 20px', borderBottom: '1px solid #1e2130', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {/* Hamburger menu for mobile */}
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              style={{
                display: window.innerWidth < 768 ? 'block' : 'none',
                background: 'none',
                border: 'none',
                color: '#9ca3af',
                cursor: 'pointer',
                fontSize: 20
              }}
            >
              ☰
            </button>
            <div style={{ fontSize: 14, color: '#9ca3af' }}>
              {active?.title || 'New conversation'}
            </div>
            {/* Tab buttons */}
            <div style={{ display: 'flex', gap: 4, marginLeft: 16 }}>
              {[
                { id: 'activity' as const, label: 'Activity', icon: '💬' },
                { id: 'llm' as const, label: 'LLM', icon: '🧠' },
                { id: 'mcps' as const, label: 'MCPs', icon: '🔧' },
                { id: 'files' as const, label: 'Files', icon: '📁' },
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    background: activeTab === tab.id ? 'rgba(99,102,241,0.15)' : 'transparent',
                    border: activeTab === tab.id ? '1px solid rgba(99,102,241,0.3)' : '1px solid transparent',
                    borderRadius: 6,
                    color: activeTab === tab.id ? '#818cf8' : '#6b7280',
                    fontSize: 11,
                    fontWeight: activeTab === tab.id ? 600 : 400,
                    padding: '4px 10px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                    transition: 'all 0.15s ease'
                  }}
                >
                  {tab.icon} {tab.label}
                </button>
              ))}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {/* Agent Mode toggle */}
            <button
              onClick={() => setAgentMode(!agentMode)}
              style={{
                background: agentMode ? 'rgba(16,185,129,0.15)' : 'transparent',
                border: agentMode ? '1px solid rgba(16,185,129,0.4)' : '1px solid #2a2d3a',
                borderRadius: 8,
                color: agentMode ? '#34d399' : '#6b7280',
                fontSize: 12,
                fontWeight: 600,
                padding: '6px 12px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 5
              }}
              title={agentMode ? 'Agent Mode ON — full autonomous pipeline' : 'Chat Mode — raw LLM'}
            >
              <span style={{ fontSize: 14 }}>{agentMode ? '⚡' : '💬'}</span>
              {agentMode ? 'Agent' : 'Chat'}
            </button>
            {/* Knowledge button */}
            <button
              onClick={() => setKnowledgeOpen(!knowledgeOpen)}
              style={{
                background: knowledgeOpen ? 'rgba(99,102,241,0.2)' : 'transparent',
                border: knowledgeOpen ? '1px solid rgba(99,102,241,0.3)' : '1px solid #2a2d3a',
                borderRadius: 8,
                color: knowledgeOpen ? '#818cf8' : '#9ca3af',
                fontSize: 12,
                padding: '6px 12px',
                cursor: 'pointer'
              }}
            >
              📚 Knowledge
            </button>
            {/* MCP button */}
            <button
              onClick={() => setMcpOpen(!mcpOpen)}
              style={{
                background: mcpOpen ? 'rgba(99,102,241,0.2)' : 'transparent',
                border: mcpOpen ? '1px solid rgba(99,102,241,0.3)' : '1px solid #2a2d3a',
                borderRadius: 8,
                color: mcpOpen ? '#818cf8' : '#9ca3af',
                fontSize: 12,
                padding: '6px 12px',
                cursor: 'pointer'
              }}
            >
              🔧 Tools
            </button>
            {/* User profile */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingLeft: 12, borderLeft: '1px solid #2a2d3a' }}>
              <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'linear-gradient(135deg, #6366f1, #818cf8)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 600, color: 'white' }}>
                {user?.email?.[0]?.toUpperCase() || 'U'}
              </div>
              <button onClick={logout} style={{ background: 'none', border: 'none', color: '#9ca3af', fontSize: 11, cursor: 'pointer' }}>Logout</button>
            </div>
          </div>
        </div>

        {/* Knowledge panel */}
        {knowledgeOpen && (
          <div style={{ padding: '12px 20px', borderBottom: '1px solid #1e2130', background: '#111318' }}>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <input
                type="text"
                value={knowledgeQuery}
                onChange={e => setKnowledgeQuery(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') searchKnowledge() }}
                placeholder="Search knowledge..."
                style={{
                  flex: 1,
                  background: '#1a1d27',
                  border: '1px solid #2a2d3a',
                  borderRadius: 8,
                  padding: '8px 12px',
                  color: '#e4e6eb',
                  fontSize: 13,
                  outline: 'none'
                }}
              />
              <button
                onClick={searchKnowledge}
                style={{
                  background: 'rgba(99,102,241,0.12)',
                  border: '1px solid rgba(99,102,241,0.3)',
                  borderRadius: 8,
                  color: '#818cf8',
                  fontSize: 13,
                  padding: '8px 16px',
                  cursor: 'pointer'
                }}
              >
                Search
              </button>
            </div>
            {knowledgeResults.length > 0 && (
              <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                {knowledgeResults.map((k, i) => (
                  <div key={i} style={{
                    background: '#1a1d27',
                    border: '1px solid #2a2d3a',
                    borderRadius: 8,
                    padding: '10px 12px',
                    marginBottom: 8
                  }}>
                    <div style={{ fontSize: 13, color: '#c7d2fe', fontWeight: 600, marginBottom: 4 }}>{k.title}</div>
                    <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 6 }}>{k.content.slice(0, 200)}...</div>
                    <div style={{ fontSize: 11, color: '#4b4f63' }}>
                      {k.keywords.join(', ')} · {k.category}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* MCP tools panel */}
        {mcpOpen && (
          <div style={{ padding: '12px 20px', borderBottom: '1px solid #1e2130', background: '#111318' }}>
            <div style={{ fontSize: 12, color: '#6366f1', fontWeight: 600, marginBottom: 8 }}>Available Tools</div>
            <div style={{ maxHeight: 200, overflowY: 'auto' }}>
              {mcpTools.map((tool, i) => (
                <div key={i} style={{
                  background: '#1a1d27',
                  border: '1px solid #2a2d3a',
                  borderRadius: 8,
                  padding: '10px 12px',
                  marginBottom: 8,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <div>
                    <div style={{ fontSize: 13, color: '#c7d2fe', fontWeight: 600 }}>{tool.name}</div>
                    <div style={{ fontSize: 11, color: '#4b4f63' }}>{tool.server_name} · {tool.description}</div>
                  </div>
                  <button
                    onClick={() => {
                      const args = prompt(`Enter arguments for ${tool.name} (JSON):`, '{}')
                      if (args) {
                        callMcpTool(tool.server_id, tool.name, JSON.parse(args))
                      }
                    }}
                    style={{
                      background: 'rgba(99,102,241,0.12)',
                      border: '1px solid rgba(99,102,241,0.3)',
                      borderRadius: 6,
                      color: '#818cf8',
                      fontSize: 11,
                      padding: '4px 10px',
                      cursor: 'pointer'
                    }}
                  >
                    Run
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab content */}
        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          {activeTab === 'activity' && (
            <div style={{ flex: 1, overflowY: 'auto', padding: '24px 0' }}>
              {messages.length === 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 16, padding: 24 }}>
                  <div style={{ fontSize: 40, fontWeight: 800, letterSpacing: '-2px', background: 'linear-gradient(135deg, #e4e6eb, #818cf8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>DevBuddy</div>
                  <p style={{ color: '#6b7280', fontSize: 16, textAlign: 'center', maxWidth: 400 }}>Describe what you want to build and I'll handle the rest.</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center', maxWidth: 500 }}>
                    {['Build a REST API with FastAPI', 'Create a React dashboard', 'Set up a CI/CD pipeline', 'Debug my Python code'].map(s => (
                      <button key={s} onClick={() => { setInput(s); textareaRef.current?.focus() }} style={{ background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 8, padding: '8px 14px', color: '#9ca3af', fontSize: 13, cursor: 'pointer' }}>{s}</button>
                    ))}
                  </div>
                </div>
              ) : (
                <div style={{ maxWidth: 760, margin: '0 auto', padding: '0 20px' }}>
                  {messages.map(msg => (
                    <div key={msg.id} style={{ marginBottom: 24, display: 'flex', gap: 12, flexDirection: msg.role === 'user' ? 'row-reverse' : 'row' }}>
                      <div style={{ width: 32, height: 32, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 700, background: msg.role === 'user' ? 'rgba(99,102,241,0.2)' : 'rgba(16,185,129,0.15)', color: msg.role === 'user' ? '#818cf8' : '#34d399' }}>
                        {msg.role === 'user' ? (user?.picture ? <img src={user.picture} alt="" style={{ width: 32, height: 32, borderRadius: '50%' }} /> : 'U') : '🤖'}
                      </div>
                      <div style={{ maxWidth: '80%', background: msg.role === 'user' ? 'rgba(99,102,241,0.1)' : '#1a1d27', border: `1px solid ${msg.role === 'user' ? 'rgba(99,102,241,0.2)' : '#2a2d3a'}`, borderRadius: 12, padding: '12px 16px' }}>
                        {msg.steps && msg.steps.length > 0 && (
                          <div style={{ marginBottom: 12, paddingBottom: 12, borderBottom: '1px solid #2a2d3a' }}>
                            <div style={{ fontSize: 11, color: '#6366f1', fontWeight: 600, marginBottom: 6 }}>
                              {msg.agentEvents && msg.agentEvents.length > 0 ? '⚡ Agent pipeline' : '🔄 Working...'}
                            </div>
                            {msg.steps.filter(s => s).map((step, i) => (
                              <div key={i} style={{ fontSize: 12, color: '#9ca3af', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                                <span style={{ color: '#6366f1' }}>→</span> {step}
                              </div>
                            ))}
                            {msg.agentEvents && msg.agentEvents.some(e => e.type === 'test') && (
                              <div style={{ marginTop: 8, padding: '6px 10px', background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', borderRadius: 6 }}>
                                {msg.agentEvents.filter(e => e.type === 'test').map((e, i) => (
                                  <div key={i} style={{ fontSize: 11, color: '#34d399' }}>
                                    ✓ {e.payload?.summary || 'Tests passed'}
                                  </div>
                                ))}
                              </div>
                            )}
                            {msg.agentEvents && msg.agentEvents.some(e => e.type === 'review') && (
                              <div style={{ marginTop: 8, padding: '6px 10px', background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 6 }}>
                                {msg.agentEvents.filter(e => e.type === 'review').map((e, i) => (
                                  <div key={i} style={{ fontSize: 11, color: '#818cf8' }}>
                                    🔍 {e.payload?.summary || 'Code reviewed'}
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
                              p: ({ children }) => <p style={{ fontSize: 14, lineHeight: 1.6, color: '#e4e6eb', marginBottom: 8 }}>{children}</p>,
                              ul: ({ children }) => <ul style={{ fontSize: 14, lineHeight: 1.6, color: '#e4e6eb', paddingLeft: 20, marginBottom: 8 }}>{children}</ul>,
                              ol: ({ children }) => <ol style={{ fontSize: 14, lineHeight: 1.6, color: '#e4e6eb', paddingLeft: 20, marginBottom: 8 }}>{children}</ol>,
                              li: ({ children }) => <li style={{ marginBottom: 4 }}>{children}</li>,
                              strong: ({ children }) => <strong style={{ color: '#c7d2fe', fontWeight: 600 }}>{children}</strong>,
                              em: ({ children }) => <em style={{ color: '#a5b4fc' }}>{children}</em>,
                              a: ({ children, href }) => <a href={href} style={{ color: '#818cf8', textDecoration: 'underline' }} target="_blank" rel="noopener noreferrer">{children}</a>,
                            }}
                          >
                            {msg.content}
                          </ReactMarkdown>
                        ) : (
                          <div style={{ fontSize: 14, lineHeight: 1.6, color: '#e4e6eb', whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                        )}
                        {msg.files && msg.files.length > 0 && (
                          <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid #2a2d3a' }}>
                            <button
                              onClick={() => downloadFiles(msg.files!)}
                              style={{
                                background: 'rgba(99,102,241,0.12)',
                                border: '1px solid rgba(99,102,241,0.3)',
                                borderRadius: 6,
                                color: '#818cf8',
                                fontSize: 12,
                                fontWeight: 600,
                                cursor: 'pointer',
                                padding: '6px 12px',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6
                              }}
                            >
                              📦 Download {msg.files.length} file{msg.files.length > 1 ? 's' : ''} as ZIP
                            </button>
                            <div style={{ marginTop: 8, fontSize: 11, color: '#4b4f63' }}>
                              {msg.files.map(f => f.name).join(', ')}
                            </div>
                          </div>
                        )}
                        <div style={{ fontSize: 11, color: '#4b4f63', marginTop: 6 }}>{new Date(msg.ts).toLocaleTimeString()}</div>
                      </div>
                    </div>
                  ))}
                  {loading && (
                    <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
                      <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'rgba(16,185,129,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14 }}>🤖</div>
                      <div style={{ background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 12, padding: '14px 18px', display: 'flex', gap: 6, alignItems: 'center' }}>
                        {[0,1,2].map(i => <div key={i} style={{ width: 8, height: 8, borderRadius: '50%', background: '#6366f1', animation: `pulse 1.2s ${i*0.2}s infinite` }} />)}
                      </div>
                    </div>
                  )}
                  <div ref={bottomRef} />
                </div>
              )}
            </div>
          )}
          
          {activeTab === 'llm' && (
            <div style={{ padding: 24, display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
              <div style={{ textAlign: 'center', color: '#6b7280' }}>
                <div style={{ fontSize: 32, marginBottom: 12 }}>🧠</div>
                <div style={{ fontSize: 14, marginBottom: 4 }}>LLM Call History</div>
                <div style={{ fontSize: 12 }}>Coming soon - will show LLM API calls with metadata</div>
              </div>
            </div>
          )}
          
          {activeTab === 'mcps' && (
            <div style={{ padding: 24, display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
              <div style={{ textAlign: 'center', color: '#6b7280' }}>
                <div style={{ fontSize: 32, marginBottom: 12 }}>🔧</div>
                <div style={{ fontSize: 14, marginBottom: 4 }}>MCP Tool Calls</div>
                <div style={{ fontSize: 12 }}>Coming soon - will show MCP tool execution history</div>
              </div>
            </div>
          )}
          
          {activeTab === 'files' && (
            <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
              {workspaceFiles.length === 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#6b7280' }}>
                  <div style={{ fontSize: 32, marginBottom: 12 }}>📁</div>
                  <div style={{ fontSize: 14, marginBottom: 4 }}>No files yet</div>
                  <div style={{ fontSize: 12 }}>Enable Agent Mode and send a task — generated files appear here live</div>
                </div>
              ) : (
                <div style={{ maxWidth: 760, margin: '0 auto' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                    <div style={{ fontSize: 13, color: '#9ca3af', fontWeight: 600 }}>{workspaceFiles.length} file{workspaceFiles.length !== 1 ? 's' : ''} generated</div>
                    {messages.some(m => m.files && m.files.length > 0) && (
                      <button
                        onClick={() => {
                          const allFiles = messages.flatMap(m => m.files || [])
                          downloadFiles(allFiles)
                        }}
                        style={{ background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.3)', borderRadius: 6, color: '#818cf8', fontSize: 12, fontWeight: 600, cursor: 'pointer', padding: '6px 12px' }}
                      >
                        📦 Download All as ZIP
                      </button>
                    )}
                  </div>
                  {workspaceFiles.map((path, i) => {
                    const fileData = messages.flatMap(m => m.files || []).find(f => f.name === path)
                    return (
                      <div key={i} style={{ background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 8, marginBottom: 8, overflow: 'hidden' }}>
                        <div style={{ padding: '10px 14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: fileData ? '1px solid #2a2d3a' : 'none' }}>
                          <div style={{ fontSize: 13, color: '#c7d2fe', fontFamily: 'monospace', fontWeight: 600 }}>{path}</div>
                          {fileData && (
                            <button
                              onClick={() => downloadFiles([fileData])}
                              style={{ background: 'none', border: 'none', color: '#6366f1', fontSize: 11, cursor: 'pointer' }}
                            >
                              ↓ Download
                            </button>
                          )}
                        </div>
                        {fileData && (
                          <pre style={{ margin: 0, padding: '10px 14px', fontSize: 12, color: '#9ca3af', fontFamily: 'monospace', overflowX: 'auto', maxHeight: 200, overflowY: 'auto' }}>
                            {fileData.content.slice(0, 2000)}{fileData.content.length > 2000 ? '\n... (truncated)' : ''}
                          </pre>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Input area */}
        <div style={{ padding: '16px 20px', borderTop: '1px solid #1e2130', flexShrink: 0 }}>
          <div style={{ maxWidth: 760, margin: '0 auto', background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 12, padding: '12px 16px', display: 'flex', gap: 12, alignItems: 'flex-end' }}>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => { setInput(e.target.value); autoResize() }}
              onKeyDown={onKeyDown}
              placeholder="Describe what you want to build..."
              rows={1}
              style={{ flex: 1, background: 'none', border: 'none', outline: 'none', color: '#e4e6eb', fontSize: 14, lineHeight: 1.5, resize: 'none', maxHeight: 200, fontFamily: 'inherit', overflowY: 'auto' }}
            />
            <button 
              onClick={loading ? cancelRequest : send} 
              disabled={!input.trim() && !loading} 
              style={{ 
                padding: '8px 16px', 
                background: loading ? 'rgba(239,68,68,0.15)' : (input.trim() ? 'linear-gradient(135deg, #6366f1, #818cf8)' : '#2a2d3a'), 
                border: loading ? '1px solid rgba(239,68,68,0.3)' : 'none', 
                borderRadius: 8, 
                color: loading ? '#f87171' : (input.trim() ? 'white' : '#4b4f63'), 
                fontSize: 14, 
                fontWeight: 600, 
                cursor: (input.trim() || loading) ? 'pointer' : 'not-allowed', 
                flexShrink: 0 
              }}
            >
              {loading ? '✕ Stop' : '↑'}
            </button>
          </div>
          <div style={{ maxWidth: 760, margin: '8px auto 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11, color: '#4b4f63' }}>
            <span>Enter to send · Shift+Enter for new line{agentMode ? ' · ⚡ Agent mode active' : ''}</span>
            <select value={model} onChange={e => setModel(e.target.value)} disabled={modelsLoading} style={{ background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 6, color: '#c7d2fe', fontSize: 11, padding: '4px 8px', cursor: modelsLoading ? 'not-allowed' : 'pointer', outline: 'none', opacity: modelsLoading ? 0.6 : 1 }}>
              {models.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
          </div>
        </div>
      </div>
    </div>
  )
}
