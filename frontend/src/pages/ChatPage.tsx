import { useState, useRef, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'

const BACKEND = import.meta.env.VITE_API_URL || ''
const API = `${BACKEND}/api/v1`

const MODELS = [
  { id: 'claude-sonnet-4', label: 'Claude Sonnet 4' },
  { id: 'llama-4-scout', label: 'Llama 4 Scout' },
  { id: 'qwen3-coder', label: 'Qwen3 Coder' },
]

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  ts: number
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
  const [model, setModel] = useState(MODELS[0].id)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const messages = active?.messages || []

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (!activeId && !loading) createNew()
  }, [])

  const autoResize = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
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

    try {
      const token = localStorage.getItem('devbuddy_token') || ''
      const resp = await fetch(`${API}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name: title, description: text, model_preference: model }),
      })
      let replyContent = ''
      if (resp.ok) {
        const data = await resp.json()
        replyContent = `Project **${data.name}** created (id: \`${data.id}\`). I'm analyzing your requirements and will begin planning the implementation.\n\n**Requirement Analysis:**\n- Task: ${text}\n- Model: ${MODELS.find(m => m.id === model)?.label}\n- Next: Breaking down into subtasks...`
      } else {
        replyContent = `Understood. I'll help you with: *${text}*\n\nI'm analyzing your requirements and preparing an action plan. What technology stack would you like to use?`
      }
      const assistantMsg: Message = { id: crypto.randomUUID(), role: 'assistant', content: replyContent, ts: Date.now() }
      updateActive([...newMsgs, assistantMsg], title)
    } catch {
      const assistantMsg: Message = {
        id: crypto.randomUUID(), role: 'assistant',
        content: `Got it — working on: *${text}*\n\nConnecting to backend... (make sure backend is running at ${BACKEND})`,
        ts: Date.now(),
      }
      updateActive([...newMsgs, assistantMsg], title)
    } finally {
      setLoading(false)
    }
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  return (
    <div style={{ display: 'flex', height: '100vh', background: '#0d0f14', color: '#e4e6eb', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' }}>

      {/* ── Left sidebar ── */}
      <div style={{ width: 260, background: '#111318', borderRight: '1px solid #1e2130', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
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
      </div>

      {/* ── Main chat area ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

        {/* Top bar */}
        <div style={{ padding: '12px 20px', borderBottom: '1px solid #1e2130', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
          <div style={{ fontSize: 14, color: '#9ca3af' }}>
            {active?.title || 'New conversation'}
          </div>
          {/* Model selector */}
          <select value={model} onChange={e => setModel(e.target.value)} style={{ background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 8, color: '#c7d2fe', fontSize: 13, padding: '6px 12px', cursor: 'pointer', outline: 'none' }}>
            {MODELS.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
          </select>
        </div>

        {/* Messages */}
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
                    <div style={{ fontSize: 14, lineHeight: 1.6, color: '#e4e6eb', whiteSpace: 'pre-wrap' }}>{msg.content}</div>
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
            <button onClick={send} disabled={!input.trim() || loading} style={{ padding: '8px 16px', background: input.trim() && !loading ? 'linear-gradient(135deg, #6366f1, #818cf8)' : '#2a2d3a', border: 'none', borderRadius: 8, color: input.trim() && !loading ? 'white' : '#4b4f63', fontSize: 14, fontWeight: 600, cursor: input.trim() && !loading ? 'pointer' : 'not-allowed', flexShrink: 0 }}>
              {loading ? '...' : '↑'}
            </button>
          </div>
          <div style={{ maxWidth: 760, margin: '8px auto 0', fontSize: 11, color: '#4b4f63', textAlign: 'center' }}>
            Enter to send · Shift+Enter for new line · Model: {MODELS.find(m => m.id === model)?.label}
          </div>
        </div>
      </div>
    </div>
  )
}
