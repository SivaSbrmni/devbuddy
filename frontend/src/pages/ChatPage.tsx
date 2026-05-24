import { useState, useRef, useEffect, useCallback, useId } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { DEV_TOKEN_KEY } from '@/lib/api'
import {
  Send, Loader2, CheckCircle2, ChevronDown, ChevronRight,
  Zap, Activity, Plug, FileText, Terminal, FolderOpen,
  Bookmark, RefreshCw, AlertCircle, Settings, XCircle,
  Download, Copy, Check, Package, Code2, Github, ExternalLink,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { LlmSettingsModal } from '@/components/LlmSettingsModal'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

type PanelTab = 'activity' | 'mcp' | 'llmlogs' | 'terminal' | 'files'

interface IntentData {
  intent: string
  confidence: number
  title: string
  description: string
  reasoning: string
  steps: string[]
  repo_id: string | null
  branch: string | null
  policy_profile: string
}

interface AgentStage {
  stage: string
  state: string
  message: string
  done: boolean
  output?: string
}

interface LlmCall {
  num: number
  model: string
  provider: string
  msgCount: number
  promptTokens: number
  completionTokens: number
  durationMs: number
  hasToolCalls: boolean
  promptPreview: string
  responsePreview: string
  error: string | null
}

interface StatusRow {
  stage: string
  text: string
  terminal: boolean   // true = done, show check; false = in-progress, show spin
}

interface ContainerLog {
  line: string
  stream: 'stdout' | 'stderr'
  ts: number
}

interface ResultFile {
  path: string
  content: string
  size: number
}

interface TaskResult {
  task_id: string
  summary: string
  files: ResultFile[]
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text?: string
  llmReply?: string
  intent?: IntentData
  needsPipeline?: boolean
  taskId?: string
  stages?: AgentStage[]
  finalState?: string
  error?: string
  streaming?: boolean
  statusRows?: StatusRow[]
  taskResult?: TaskResult
}

const SUGGESTIONS = [
  'Add rate limiting middleware to the authentication service',
  'Fix the memory leak in the background job processor',
  'Refactor the user onboarding flow to use async/await',
  'Add OpenTelemetry tracing to all API endpoints',
  'Review and harden the SQL query builder for injection risks',
]

function AgentEventRow({ text, icon, expanded, onToggle, children }: {
  text: string
  icon: 'spin' | 'check' | 'info' | 'intent' | 'warn'
  expanded?: boolean
  onToggle?: () => void
  children?: React.ReactNode
}) {
  const hasContent = !!children
  return (
    <div className="rounded-lg border border-white/8 bg-white/3 overflow-hidden">
      <button
        onClick={hasContent ? onToggle : undefined}
        className={cn(
          'w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors',
          hasContent ? 'hover:bg-white/5 cursor-pointer' : 'cursor-default'
        )}
      >
        <span className="shrink-0">
          {icon === 'spin'   && <Loader2 className="w-3.5 h-3.5 text-teal-400 animate-spin" />}
          {icon === 'check'  && <CheckCircle2 className="w-3.5 h-3.5 text-teal-400" />}
          {icon === 'info'   && <Zap className="w-3.5 h-3.5 text-teal-300" />}
          {icon === 'intent' && <Activity className="w-3.5 h-3.5 text-amber-400" />}
          {icon === 'warn'   && <AlertCircle className="w-3.5 h-3.5 text-amber-400" />}
        </span>
        <span className="flex-1 text-xs text-slate-300">{text}</span>
        {hasContent && (
          expanded
            ? <ChevronDown className="w-3 h-3 text-slate-500 shrink-0" />
            : <ChevronRight className="w-3 h-3 text-slate-500 shrink-0" />
        )}
      </button>
      {hasContent && expanded && (
        <div className="px-4 pb-3 pt-1 border-t border-white/8 bg-white/2">
          {children}
        </div>
      )}
    </div>
  )
}

function IntentAnalysisCard({ intent, expanded, onToggle }: {
  intent: IntentData; expanded: boolean; onToggle: () => void
}) {
  const pct = Math.round(intent.confidence * 100)
  return (
    <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-white/3 transition-colors"
      >
        <Activity className="w-3.5 h-3.5 text-amber-400 shrink-0" />
        <span className="text-xs font-semibold text-slate-200 flex-1">INTENT ANALYSIS</span>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/30 text-amber-300 font-mono border border-amber-500/30 mr-2">
          {intent.intent.replace('_', ' ')} · {pct}%
        </span>
        {expanded
          ? <ChevronDown className="w-3 h-3 text-slate-500 shrink-0" />
          : <ChevronRight className="w-3 h-3 text-slate-500 shrink-0" />}
      </button>
      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-amber-500/15 space-y-3">
          <p className="text-xs text-teal-300 font-medium mt-2">▷ {intent.title}</p>

          {intent.steps.length > 0 && (
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1.5">Requirements</p>
              {intent.steps.map((s, i) => (
                <div key={i} className="flex items-start gap-2 mb-1">
                  <span className="text-teal-400 text-xs mt-0.5">→</span>
                  <span className="text-xs text-slate-300">{s}</span>
                </div>
              ))}
            </div>
          )}

          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1.5">Assumptions</p>
            <div className="flex items-start gap-2 mb-1">
              <span className="text-slate-500 text-xs mt-0.5">◎</span>
              <span className="text-xs text-slate-400">{intent.reasoning}</span>
            </div>
            {intent.branch && (
              <div className="flex items-start gap-2">
                <span className="text-slate-500 text-xs mt-0.5">◎</span>
                <span className="text-xs text-slate-400 font-mono">branch: {intent.branch}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function LlmLogsPanel({ calls }: { calls: LlmCall[] }) {
  const [expanded, setExpanded] = useState<number | null>(null)
  if (calls.length === 0) return (
    <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-2">
      <FileText className="w-8 h-8 opacity-30" />
      <p className="text-sm">No LLM calls yet</p>
    </div>
  )
  return (
    <div className="p-4 space-y-1.5 overflow-y-auto h-full scrollbar-thin">
      <p className="text-[10px] text-slate-500 mb-3">{calls.length} {calls.length === 1 ? 'call' : 'calls'}</p>
      {calls.map(c => {
        const isOpen = expanded === c.num
        const totalTokens = (c.promptTokens || 0) + (c.completionTokens || 0)
        return (
          <div key={c.num} className="rounded-lg border border-white/8 bg-white/3 overflow-hidden">
            <button
              onClick={() => setExpanded(isOpen ? null : c.num)}
              className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-white/5 transition-colors text-left"
            >
              <span className="text-slate-400 text-xs">⇄</span>
              <span className="text-xs font-semibold text-slate-200">LLM Call #{c.num}</span>
              <span className="text-[10px] font-mono bg-teal-500/20 text-teal-300 px-2 py-0.5 rounded border border-teal-500/30">
                {c.model}
              </span>
              <span className="text-[10px] text-slate-500">{c.msgCount} msgs in</span>
              {c.hasToolCalls && <span className="text-[10px] font-mono text-orange-400">→ tool_calls</span>}
              {c.error && <span className="text-[10px] text-red-400">✕ error</span>}
              {totalTokens > 0 && <span className="text-[10px] text-slate-600">{totalTokens} tok</span>}
              {c.durationMs > 0 && <span className="text-[10px] text-slate-600">{c.durationMs.toFixed(0)}ms</span>}
              <span className="ml-auto">
                {isOpen
                  ? <ChevronDown className="w-3 h-3 text-slate-500" />
                  : <ChevronRight className="w-3 h-3 text-slate-500" />}
              </span>
            </button>
            {isOpen && (
              <div className="px-4 pb-4 pt-2 border-t border-white/8 space-y-3 bg-white/2">
                <div className="flex gap-4 flex-wrap">
                  <span className="text-[10px] text-slate-500">provider: <span className="text-teal-400 font-mono">{c.provider}</span></span>
                  {c.promptTokens > 0 && <span className="text-[10px] text-slate-500">prompt: <span className="text-slate-300">{c.promptTokens}</span></span>}
                  {c.completionTokens > 0 && <span className="text-[10px] text-slate-500">completion: <span className="text-slate-300">{c.completionTokens}</span></span>}
                  {c.durationMs > 0 && <span className="text-[10px] text-slate-500">latency: <span className="text-slate-300">{c.durationMs.toFixed(0)}ms</span></span>}
                </div>
                {c.promptPreview && (
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Prompt</p>
                    <pre className="text-[10px] text-slate-400 bg-black/30 rounded p-2 whitespace-pre-wrap break-words font-mono leading-relaxed overflow-x-hidden">{c.promptPreview}</pre>
                  </div>
                )}
                {c.responsePreview && (
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Response</p>
                    <pre className="text-[10px] text-teal-300 bg-black/30 rounded p-2 whitespace-pre-wrap break-words font-mono leading-relaxed overflow-x-hidden">{c.responsePreview}</pre>
                  </div>
                )}
                {c.error && (
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Error</p>
                    <p className="text-[10px] text-red-400 font-mono">{c.error}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── language detection ───────────────────────────────────────────────────────
function detectLang(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase() ?? ''
  const MAP: Record<string, string> = {
    py: 'Python', ts: 'TypeScript', tsx: 'TSX', js: 'JavaScript', jsx: 'JSX',
    json: 'JSON', yaml: 'YAML', yml: 'YAML', md: 'Markdown', sh: 'Shell',
    bash: 'Shell', css: 'CSS', html: 'HTML', go: 'Go', rs: 'Rust',
    java: 'Java', kt: 'Kotlin', rb: 'Ruby', php: 'PHP', sql: 'SQL', toml: 'TOML',
  }
  return MAP[ext] ?? (ext.toUpperCase() || 'Text')
}

function langColor(lang: string): string {
  const MAP: Record<string, string> = {
    Python: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
    TypeScript: 'bg-sky-500/20 text-sky-300 border-sky-500/30',
    TSX: 'bg-sky-500/20 text-sky-300 border-sky-500/30',
    JavaScript: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
    JSX: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
    JSON: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
    Shell: 'bg-green-500/20 text-green-300 border-green-500/30',
    Markdown: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
    Go: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
    Rust: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
  }
  return MAP[lang] ?? 'bg-purple-500/20 text-purple-300 border-purple-500/30'
}

// ── TaskResultPanel ───────────────────────────────────────────────────────────
function TaskResultPanel({ result }: { result: TaskResult }) {
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set())
  const [copied, setCopied] = useState<string | null>(null)

  const toggleFile = (path: string) => {
    setExpandedFiles(prev => {
      const next = new Set(prev)
      next.has(path) ? next.delete(path) : next.add(path)
      return next
    })
  }

  const copyFile = async (content: string, path: string) => {
    await navigator.clipboard.writeText(content)
    setCopied(path)
    setTimeout(() => setCopied(null), 2000)
  }

  const downloadFile = (content: string, filename: string) => {
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename.split('/').pop() ?? filename
    a.click()
    URL.revokeObjectURL(url)
  }

  const downloadAll = () => {
    result.files.forEach(f => downloadFile(f.content, f.path))
  }

  // Only show root-level files (not subtask-N/ dirs)
  const rootFiles = result.files.filter(f => !f.path.includes('/subtask-'))
  const displayFiles = rootFiles.length > 0 ? rootFiles : result.files.slice(0, 6)

  return (
    <div className="mt-3 rounded-xl border border-teal-500/25 bg-[#071624] overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-teal-500/8 border-b border-teal-500/20">
        <div className="w-7 h-7 rounded-lg bg-teal-500/20 flex items-center justify-center shrink-0">
          <Package className="w-3.5 h-3.5 text-teal-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-bold text-teal-300">Task Artifacts</p>
          <p className="text-[10px] text-teal-500">{displayFiles.length} file{displayFiles.length !== 1 ? 's' : ''} generated</p>
        </div>
        <button
          onClick={downloadAll}
          className="flex items-center gap-1.5 text-[11px] text-teal-400 hover:text-teal-200 border border-teal-500/30 rounded-lg px-2.5 py-1.5 hover:bg-teal-500/15 transition-colors shrink-0"
          title="Download all files"
        >
          <Download className="w-3 h-3" />
          <span className="hidden sm:inline">Download all</span>
        </button>
      </div>

      {/* Summary */}
      {result.summary && (
        <div className="px-4 py-3 border-b border-white/6">
          <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500 mb-1.5">Completion Summary</p>
          <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap">{result.summary.replace(/\*\*/g, '').trim()}</p>
        </div>
      )}

      {/* File list */}
      <div className="divide-y divide-white/6">
        {displayFiles.map(f => {
          const lang = detectLang(f.path)
          const isOpen = expandedFiles.has(f.path)
          const lines = f.content.split('\n').length
          const isCopied = copied === f.path
          return (
            <div key={f.path}>
              {/* File row */}
              <div className="flex items-center gap-2 px-4 py-2.5 hover:bg-white/3 transition-colors">
                <button
                  onClick={() => toggleFile(f.path)}
                  className="flex items-center gap-2 flex-1 min-w-0 text-left"
                >
                  <Code2 className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                  <span className="text-[11px] font-mono text-slate-200 truncate flex-1">
                    {f.path.split('/').pop()}
                  </span>
                  <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border shrink-0 ${langColor(lang)}`}>
                    {lang}
                  </span>
                  <span className="text-[10px] text-slate-600 shrink-0">{lines}L · {formatBytes(f.size)}</span>
                  {isOpen
                    ? <ChevronDown className="w-3 h-3 text-slate-600 shrink-0" />
                    : <ChevronRight className="w-3 h-3 text-slate-600 shrink-0" />}
                </button>
                <button
                  onClick={() => copyFile(f.content, f.path)}
                  className="p-1.5 rounded hover:bg-white/8 text-slate-500 hover:text-teal-400 transition-colors shrink-0"
                  title="Copy"
                >
                  {isCopied ? <Check className="w-3 h-3 text-teal-400" /> : <Copy className="w-3 h-3" />}
                </button>
                <button
                  onClick={() => downloadFile(f.content, f.path)}
                  className="p-1.5 rounded hover:bg-white/8 text-slate-500 hover:text-teal-400 transition-colors shrink-0"
                  title="Download"
                >
                  <Download className="w-3 h-3" />
                </button>
              </div>
              {/* Code preview */}
              {isOpen && (
                <div className="bg-[#030810] border-t border-white/6">
                  <pre className="p-4 text-[11px] text-slate-300 font-mono leading-relaxed whitespace-pre overflow-x-auto scrollbar-thin max-h-[60vh]">
                    {f.content}
                  </pre>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function TerminalPanel({ logs }: { logs: ContainerLog[] }) {
  const bottomRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  if (logs.length === 0) return (
    <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-3">
      <Terminal className="w-8 h-8 opacity-30" />
      <p className="text-sm">No container output yet — send a coding task to start</p>
    </div>
  )
  return (
    <div className="h-full overflow-y-auto bg-[#030810] p-4 font-mono scrollbar-thin">
      <p className="text-[10px] text-slate-600 mb-2">{logs.length} lines</p>
      {logs.map((l, i) => (
        <div key={i} className="flex gap-2 leading-5">
          <span className="text-[10px] text-slate-700 shrink-0 w-16 text-right">
            {new Date(l.ts * 1000).toISOString().slice(11, 19)}
          </span>
          <span className={`text-[11px] whitespace-pre-wrap break-words ${
            l.stream === 'stderr' ? 'text-red-400' :
            l.line.startsWith('[write]') ? 'text-teal-300' :
            l.line.startsWith('[lint]') || l.line.startsWith('[build]') ? 'text-amber-300' :
            'text-slate-300'
          }`}>{l.line}</span>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}

interface WorkspaceFile { type: 'file' | 'dir'; path: string; name: string; size?: number; children?: WorkspaceFile[] }

function formatBytes(b: number) {
  if (b < 1024) return `${b}b`
  if (b < 1024 * 1024) return `${(b/1024).toFixed(1)}kb`
  return `${(b/(1024*1024)).toFixed(1)}mb`
}

function FilesPanel({ taskId, refreshKey }: { taskId?: string; refreshKey?: number }) {
  const [files, setFiles] = useState<WorkspaceFile[]>([])
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [openFile, setOpenFile] = useState<{ path: string; content: string } | null>(null)

  const openFileContent = useCallback(async (path: string) => {
    if (!taskId) return
    const token = localStorage.getItem('devbuddy_dev_token')
    const headers: Record<string, string> = {}
    if (token) headers['Authorization'] = `Bearer ${token}`
    try {
      const res = await fetch(`${API_BASE}/api/v1/workspace/result/${taskId}`, { headers })
      if (res.ok) {
        const data = await res.json()
        const f = data.files?.find((f: { path: string; content: string }) => f.path === path)
        if (f) setOpenFile({ path: f.path, content: f.content })
      }
    } catch { /* silent */ }
  }, [taskId])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const token = localStorage.getItem('devbuddy_dev_token')
      const headers: Record<string, string> = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      const url = taskId
        ? `${API_BASE}/api/v1/workspace/files?task_id=${taskId}`
        : `${API_BASE}/api/v1/workspace/files`
      const res = await fetch(url, { headers })
      if (res.ok) {
        const data = await res.json()
        setFiles(data.files ?? [])
      }
    } catch { /* silent */ }
    finally { setLoading(false) }
  }, [taskId])

  useEffect(() => { load() }, [load, refreshKey])

  const toggleDir = (path: string) => setExpanded(prev => {
    const n = new Set(prev); n.has(path) ? n.delete(path) : n.add(path); return n
  })

  const renderEntries = (entries: WorkspaceFile[], depth = 0): React.ReactNode =>
    entries.map(e => (
      <div key={e.path} style={{ paddingLeft: depth * 12 }}>
        {e.type === 'dir' ? (
          <>
            <button
              onClick={() => toggleDir(e.path)}
              className="flex items-center gap-1.5 w-full py-0.5 text-left hover:text-slate-200 text-slate-400 transition-colors"
            >
              {expanded.has(e.path)
                ? <ChevronDown className="w-3 h-3 shrink-0" />
                : <ChevronRight className="w-3 h-3 shrink-0" />}
              <FolderOpen className="w-3 h-3 text-amber-400 shrink-0" />
              <span className="text-[11px] font-medium">{e.name}</span>
            </button>
            {expanded.has(e.path) && e.children && renderEntries(e.children, depth + 1)}
          </>
        ) : (
          <button
            onClick={() => openFileContent(e.path)}
            className="w-full flex items-center gap-1.5 py-1 pl-4 hover:bg-white/5 rounded transition-colors text-left"
          >
            <FileText className="w-3 h-3 text-slate-500 shrink-0" />
            <span className="text-[11px] text-slate-300 truncate flex-1">{e.name}</span>
            {e.size !== undefined && <span className="text-[10px] text-slate-600 shrink-0 mr-2">{formatBytes(e.size)}</span>}
          </button>
        )}
      </div>
    ))

  if (loading) return (
    <div className="flex items-center justify-center h-full gap-2 text-slate-500">
      <Loader2 className="w-4 h-4 animate-spin" />
      <span className="text-sm">Loading workspace...</span>
    </div>
  )

  if (files.length === 0) return (
    <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-3">
      <FolderOpen className="w-8 h-8 opacity-30" />
      <p className="text-sm">No files in workspace yet</p>
      <button onClick={load} className="flex items-center gap-1.5 text-xs text-teal-400 hover:text-teal-300 transition-colors">
        <RefreshCw className="w-3 h-3" />
        Refresh
      </button>
    </div>
  )

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* File viewer overlay */}
      {openFile && (
        <div className="absolute inset-0 z-10 flex flex-col bg-[#070f1e] border-l border-white/8">
          <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/8 bg-[#0a1525] shrink-0">
            <FileText className="w-3.5 h-3.5 text-teal-400 shrink-0" />
            <span className="text-xs text-slate-300 font-mono flex-1 truncate">{openFile.path}</span>
            <button onClick={() => setOpenFile(null)} className="p-1 rounded hover:bg-white/8 text-slate-400 hover:text-slate-200">
              <XCircle className="w-3.5 h-3.5" />
            </button>
          </div>
          <pre className="flex-1 overflow-auto p-4 text-[11px] text-slate-300 font-mono leading-relaxed whitespace-pre scrollbar-thin">
            {openFile.content}
          </pre>
        </div>
      )}
      <div className="flex items-center justify-between px-4 py-2 border-b border-white/8 shrink-0">
        <p className="text-[10px] text-slate-500">{files.length} entries · {taskId?.slice(0,8)}</p>
        <button onClick={load} className="flex items-center gap-1 text-[10px] text-teal-400 hover:text-teal-300">
          <RefreshCw className="w-2.5 h-2.5" /> Refresh
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-2 scrollbar-thin">
        {renderEntries(files)}
      </div>
    </div>
  )
}

function AgentConversation({ msg, expandedRows, toggleRow }: {
  msg: ChatMessage
  expandedRows: Set<string>
  toggleRow: (key: string) => void
}) {
  const stages = msg.stages ?? []
  const isDone = !msg.streaming

  return (
    <div className="space-y-1">

      {/* ── Status rows (intent analysis, task creation) ── */}
      {msg.statusRows?.map((r, i) => {
        const resolved = r.terminal || isDone
        return (
          <div key={`sr-${i}`} className="flex items-center gap-2.5 px-1 py-1">
            <span className="shrink-0 w-4">
              {resolved
                ? <CheckCircle2 className="w-3.5 h-3.5 text-teal-400" />
                : <Loader2 className="w-3.5 h-3.5 text-teal-400 animate-spin" />}
            </span>
            <span className="text-xs text-slate-400">{r.text}</span>
          </div>
        )
      })}

      {/* ── Intent analysis card ── */}
      {msg.intent && (
        <IntentAnalysisCard
          intent={msg.intent}
          expanded={expandedRows.has(`${msg.id}-intent`)}
          onToggle={() => toggleRow(`${msg.id}-intent`)}
        />
      )}

      {/* ── Direct LLM reply (no pipeline) ── */}
      {msg.llmReply && (
        <div className="mt-2 px-4 py-3 rounded-xl border border-teal-500/20 bg-teal-500/5">
          <p className="text-sm text-slate-200 leading-relaxed">{msg.llmReply}</p>
        </div>
      )}

      {/* ── Agent pipeline stages (indented subprocess view) ── */}
      {stages.length > 0 && (
        <div className="mt-1">
          {/* Pipeline header */}
          <div className="flex items-center gap-2 px-1 py-1.5">
            <span className="shrink-0">
              {isDone
                ? <CheckCircle2 className="w-3.5 h-3.5 text-teal-400" />
                : <Loader2 className="w-3.5 h-3.5 text-teal-400 animate-spin" />}
            </span>
            <span className="text-xs font-semibold text-slate-300">Agent Pipeline</span>
            {isDone && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-teal-500/20 text-teal-300 border border-teal-500/30">
                {msg.finalState ?? 'COMPLETED'}
              </span>
            )}
          </div>

          {/* Indented stage list */}
          <div className="ml-5 border-l border-white/8 pl-3 space-y-0.5">
            {stages.map((s, i) => {
              const stageKey = `${msg.id}-stage-${i}`
              const isExpanded = expandedRows.has(stageKey)
              const stageDone = s.done || isDone
              return (
                <div key={stageKey} className="rounded-lg border border-white/6 bg-white/2 overflow-hidden">
                  <button
                    onClick={() => toggleRow(stageKey)}
                    className="w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-white/4 transition-colors"
                  >
                    <span className="shrink-0">
                      {stageDone
                        ? <CheckCircle2 className="w-3 h-3 text-teal-400" />
                        : <Loader2 className="w-3 h-3 text-teal-400 animate-spin" />}
                    </span>
                    <span className="flex-1 text-[11px] text-slate-300">{s.message}</span>
                    <span className="text-[10px] font-mono text-slate-600 shrink-0">{s.stage}</span>
                    {isExpanded
                      ? <ChevronDown className="w-3 h-3 text-slate-600 shrink-0" />
                      : <ChevronRight className="w-3 h-3 text-slate-600 shrink-0" />}
                  </button>
                  {isExpanded && (
                    <div className="px-3 pb-3 pt-2 border-t border-white/6 bg-black/10 space-y-2">
                      {/* metadata strip */}
                      <div className="flex items-center gap-3">
                        <span className="text-[10px] font-mono text-slate-600">state:</span>
                        <span className="text-[10px] font-mono text-teal-400">{s.state}</span>
                        <span className="text-[10px] font-mono text-slate-600">status:</span>
                        <span className={`text-[10px] font-mono ${stageDone ? 'text-teal-400' : 'text-amber-400'}`}>
                          {stageDone ? 'done' : 'running'}
                        </span>
                      </div>
                      {/* LLM output */}
                      {s.output ? (
                        <pre className="text-[11px] text-slate-300 bg-[#060d1a] border border-white/6 rounded-lg p-3 whitespace-pre-wrap break-words font-mono leading-relaxed overflow-x-hidden">
                          {s.output}
                        </pre>
                      ) : !stageDone ? (
                        <div className="flex items-center gap-2 text-[11px] text-slate-500">
                          <Loader2 className="w-3 h-3 animate-spin" />
                          <span>Working...</span>
                        </div>
                      ) : null}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Error row ── */}
      {msg.error && (
        <div className="flex items-center gap-2 px-1 mt-1">
          <AlertCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />
          <p className="text-xs text-red-400">{msg.error}</p>
        </div>
      )}

      {/* ── Task artifacts (shown after pipeline completes) ── */}
      {msg.taskResult && isDone && (
        <TaskResultPanel result={msg.taskResult} />
      )}
    </div>
  )
}

export function ChatPage() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState<PanelTab>('activity')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [taskTitle, setTaskTitle] = useState<string>('')
  const [saved, setSaved] = useState(false)
  const [llmCalls, setLlmCalls] = useState<LlmCall[]>([])
  const [containerLogs, setContainerLogs] = useState<ContainerLog[]>([])
  const [activeTaskId, setActiveTaskId] = useState<string | undefined>()
  const activeTaskIdRef = useRef<string | undefined>()
  const [filesRefreshKey, setFilesRefreshKey] = useState(0)
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [llmLabel, setLlmLabel] = useState('llama3.2')
  const [mcpConns, setMcpConns] = useState<{id:string;name:string;conn_type:string;is_active:boolean;last_test_ok:boolean|null}[]>([])
  const [githubRepos, setGithubRepos] = useState<{id:string;name:string;repo_url:string;clone_status:string|null}[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const navigate = useNavigate()

  // Keyboard shortcuts: Ctrl/Cmd+/ = focus input, Ctrl/Cmd+N = clear new chat
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey
      if (mod && e.key === '/') { e.preventDefault(); inputRef.current?.focus() }
      if (mod && e.key === 'k') { e.preventDefault(); inputRef.current?.focus() }
      if (mod && e.key === 'n') {
        e.preventDefault()
        if (!busy) { setMessages([]); setInput(''); setActiveTab('activity'); inputRef.current?.focus() }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [busy])

  useEffect(() => {
    const token = localStorage.getItem(DEV_TOKEN_KEY)
    const headers: Record<string, string> = {}
    if (token) headers['Authorization'] = `Bearer ${token}`
    fetch(`${API_BASE}/api/v1/llm/config`, { headers })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setLlmLabel(`${d.provider}/${d.model}`) })
      .catch(() => {})
    // Load MCP + GitHub connections for the MCP panel
    fetch(`${API_BASE}/api/v1/mcp/connections`, { headers })
      .then(r => r.ok ? r.json() : [])
      .then(d => setMcpConns(d))
      .catch(() => {})
    fetch(`${API_BASE}/api/v1/github/connections`, { headers })
      .then(r => r.ok ? r.json() : [])
      .then(d => setGithubRepos(d))
      .catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const toggleRow = useCallback((key: string) => {
    setExpandedRows(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }, [])

  const updateMsg = useCallback((id: string, patch: Partial<ChatMessage>) => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, ...patch } : m))
  }, [])

  const upsertStatusRow = useCallback((id: string, stage: string, text: string, terminal: boolean) => {
    setMessages(prev => prev.map(m => {
      if (m.id !== id) return m
      const existing = m.statusRows ?? []
      const idx = existing.findIndex(r => r.stage === stage)
      if (idx >= 0) {
        const updated = [...existing]
        updated[idx] = { stage, text, terminal }
        return { ...m, statusRows: updated }
      }
      return { ...m, statusRows: [...existing, { stage, text, terminal }] }
    }))
  }, [])

  const send = useCallback(async (text: string) => {
    if (!text.trim() || busy) return
    setBusy(true)
    setSaved(false)

    const asstMsgId = `a-${Date.now()}`

    setMessages(prev => [
      ...prev,
      { id: `u-${Date.now()}`, role: 'user', text: text.trim() },
      { id: asstMsgId, role: 'assistant', streaming: true, statusRows: [], stages: [] },
    ])
    setInput('')

    try {
      const token = localStorage.getItem(DEV_TOKEN_KEY)
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const resp = await fetch(`${API_BASE}/api/v1/chat`, {
        method: 'POST', headers,
        body: JSON.stringify({ message: text.trim() }),
      })
      if (!resp.ok) throw new Error(`Server error ${resp.status}`)

      const reader = resp.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let stages: AgentStage[] = []

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''

        for (const part of parts) {
          const lines = part.split('\n')
          if (lines.every(l => l.startsWith(':') || l === '')) continue  // heartbeat
          const evLine = lines.find(l => l.startsWith('event:'))
          const dataLine = lines.find(l => l.startsWith('data:'))
          if (!evLine || !dataLine) continue
          const evType = evLine.replace('event:', '').trim()
          const payload = JSON.parse(dataLine.replace('data:', '').trim())

          if (evType === 'status') {
            upsertStatusRow(asstMsgId, payload.stage, payload.message, payload.terminal === true)
          }

          if (evType === 'warning') {
            upsertStatusRow(asstMsgId, `warn-${payload.stage}`, `⚠ ${payload.message}`, true)
          }

          if (evType === 'error') {
            const label = payload.recoverable ? `↩ ${payload.message}` : `✕ ${payload.message}`
            upsertStatusRow(asstMsgId, `err-${payload.stage}`, label, true)
          }

          if (evType === 'llm_call') {
            const call: LlmCall = {
              num:              payload.num,
              model:            payload.model,
              provider:         payload.provider,
              msgCount:         payload.msg_count,
              promptTokens:     payload.prompt_tokens,
              completionTokens: payload.completion_tokens,
              durationMs:       payload.duration_ms,
              hasToolCalls:     payload.has_tool_calls,
              promptPreview:    payload.prompt_preview,
              responsePreview:  payload.response_preview,
              error:            payload.error,
            }
            setLlmCalls(prev => [...prev, call])
          }

          if (evType === 'intent') {
            updateMsg(asstMsgId, {
              intent: payload,
              needsPipeline: payload.needs_pipeline,
              streaming: true,
            })
            setExpandedRows(prev => new Set([...prev, `${asstMsgId}-intent`]))
          }

          if (evType === 'llm_reply') {
            updateMsg(asstMsgId, { llmReply: payload.text, streaming: false })
          }

          if (evType === 'container_log') {
            setContainerLogs(prev => {
              if (prev.length === 0) setActiveTab('terminal') // auto-switch to terminal on first log
              return [...prev, { line: payload.line, stream: payload.stream, ts: payload.ts }]
            })
          }

          if (evType === 'task_created') {
            setTaskTitle(payload.title)
            setActiveTaskId(payload.task_id)
            activeTaskIdRef.current = payload.task_id
            setContainerLogs([])  // clear previous run logs
            upsertStatusRow(asstMsgId, 'sandbox', `Sandbox ready · task ${payload.task_id.slice(0, 8)}`, true)
            upsertStatusRow(asstMsgId, 'workspace', 'Workspace ready', true)
            updateMsg(asstMsgId, { taskId: payload.task_id })
          }

          if (evType === 'agent_stage') {
            stages = [...stages, { stage: payload.stage, state: payload.state, message: payload.message, done: false, output: '' }]
            updateMsg(asstMsgId, { stages: [...stages] })
          }

          if (evType === 'state_update') {
            stages = stages.map(s =>
              s.state === payload.state
                ? { ...s, done: true, output: payload.output ?? s.output }
                : s
            )
            updateMsg(asstMsgId, { stages: [...stages] })
          }

          if (evType === 'done') {
            stages = stages.map(s => ({ ...s, done: true }))
            updateMsg(asstMsgId, {
              stages: [...stages],
              finalState: payload.final_state,
              streaming: false,
            })
            if (payload.final_state !== 'ANSWERED') {
              setSaved(true)
              setFilesRefreshKey(k => k + 1)
              // Fetch artifacts and attach to the message
              const tid = activeTaskIdRef.current
              if (tid) {
                const tok = localStorage.getItem(DEV_TOKEN_KEY)
                const hdrs: Record<string, string> = {}
                if (tok) hdrs['Authorization'] = `Bearer ${tok}`
                fetch(`${API_BASE}/api/v1/workspace/result/${tid}`, { headers: hdrs })
                  .then(r => r.ok ? r.json() : null)
                  .then(data => {
                    if (data && data.files?.length) {
                      updateMsg(asstMsgId, { taskResult: data as TaskResult })
                    }
                  })
                  .catch(() => {})
              }
            }
          }
        }
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Unknown error'
      updateMsg(asstMsgId, { error: errMsg, streaming: false })
    } finally {
      setBusy(false)
      inputRef.current?.focus()
    }
  }, [busy, updateMsg, upsertStatusRow])

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input) }
  }

  const TOOLBAR_TABS: { id: PanelTab; label: string; icon: React.ElementType }[] = [
    { id: 'activity',  label: 'Activity',   icon: Activity  },
    { id: 'mcp',       label: 'MCP Tools',  icon: Plug      },
    { id: 'llmlogs',   label: 'LLM Logs',   icon: FileText  },
    { id: 'terminal',  label: '',           icon: Terminal  },
    { id: 'files',     label: 'Files',      icon: FolderOpen},
  ]

  const activeMessages = messages.filter(m => m.role === 'user' || m.role === 'assistant')

  return (
    <div className="flex flex-col h-full bg-[#070f1e] text-slate-100 overflow-hidden">

      {/* ── TOP TOOLBAR ─────────────────────────────────────────── */}
      <div className="flex items-center gap-1.5 px-3 py-2 border-b border-white/8 bg-[#0a1525] shrink-0 overflow-x-auto scrollbar-none">
        {/* Task title — hidden on xs */}
        <span className="hidden sm:block text-xs text-slate-400 truncate max-w-[160px] shrink-0">
          {taskTitle || 'New task'}
        </span>

        <div className="hidden sm:block flex-1" />

        {/* Saved pill */}
        <button
          onClick={() => setSaved(s => !s)}
          className={cn(
            'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold border transition-colors shrink-0',
            saved
              ? 'bg-teal-500/20 text-teal-300 border-teal-500/40'
              : 'bg-white/5 text-slate-400 border-white/10 hover:text-slate-300'
          )}
        >
          <Bookmark className="w-3 h-3" />
          <span className="hidden sm:inline">{saved ? 'Saved' : 'Save'}</span>
        </button>

        {/* Tab pills — scroll horizontally on mobile */}
        {TOOLBAR_TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={cn(
              'flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors shrink-0',
              activeTab === t.id
                ? 'bg-teal-500/20 text-teal-200 border-teal-500/40'
                : 'bg-white/5 text-slate-400 border-white/8 hover:text-slate-300 hover:bg-white/8'
            )}
            title={t.id}
          >
            <t.icon className="w-3.5 h-3.5" />
            {t.label && <span className="hidden sm:inline">{t.label}</span>}
          </button>
        ))}

        {/* Live dot */}
        <div className="flex items-center gap-1 ml-1 shrink-0">
          <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse" />
          <span className="hidden sm:inline text-[10px] text-teal-400">Live</span>
        </div>
      </div>

      {/* ── MAIN AREA ───────────────────────────────────────────── */}
      <div className="flex-1 overflow-hidden">

        {/* Activity tab = chat execution view */}
        {activeTab === 'activity' && (
          <div className="flex flex-col h-full">
            <div className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 sm:py-5 space-y-4 sm:space-y-5 scrollbar-thin">

              {/* Empty state */}
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full gap-6 py-16">
                  <div className="w-12 h-12 rounded-full bg-teal-500/20 border border-teal-500/30 flex items-center justify-center">
                    <Zap className="w-5 h-5 text-teal-400" />
                  </div>
                  <div className="text-center">
                    <p className="text-base font-semibold text-slate-200">
                      Hi{user?.email ? ` ${user.email.split('@')[0]}` : ''}
                    </p>
                    <p className="text-sm text-slate-500 mt-1">Describe a coding task to get started</p>
                  </div>
                  <div className="flex flex-wrap gap-2 justify-center max-w-xl">
                    {SUGGESTIONS.map(s => (
                      <button
                        key={s}
                        onClick={() => send(s)}
                        className="text-xs text-slate-400 border border-white/10 rounded-lg px-3 py-2 hover:border-teal-500/40 hover:text-slate-200 hover:bg-white/5 transition-colors flex items-center gap-1.5"
                      >
                        <ChevronRight className="w-3 h-3 text-teal-400" />
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {activeMessages.map(msg => (
                <div key={msg.id}>
                  {msg.role === 'user' ? (
                    /* User bubble — top right, teal bg */
                    <div className="flex justify-end">
                      <div className="max-w-[90%] sm:max-w-[75%] bg-teal-600/60 border border-teal-500/30 text-white text-sm px-4 py-2.5 rounded-2xl rounded-tr-sm leading-relaxed">
                        {msg.text}
                      </div>
                    </div>
                  ) : (
                    /* Agent response — collapsible event rows */
                    <AgentConversation
                      msg={msg}
                      expandedRows={expandedRows}
                      toggleRow={toggleRow}
                    />
                  )}
                </div>
              ))}

              <div ref={bottomRef} />
            </div>

            {/* ── BOTTOM INPUT ────────────────────────────────────── */}
            <div className="px-3 sm:px-6 py-3 sm:py-4 shrink-0">
              <div className="rounded-2xl border border-teal-500/30 bg-[#0d2035] shadow-lg shadow-teal-900/20 overflow-hidden">
                <div className="px-4 py-3">
                  <textarea
                    ref={inputRef}
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={handleKey}
                    placeholder="Describe a coding task..."
                    disabled={busy}
                    rows={1}
                    className="w-full resize-none bg-transparent text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none disabled:opacity-50 max-h-32 leading-relaxed"
                    onInput={e => {
                      const t = e.currentTarget
                      t.style.height = 'auto'
                      t.style.height = `${Math.min(t.scrollHeight, 128)}px`
                    }}
                  />
                </div>
                <div className="flex items-center gap-2 px-4 py-2 border-t border-white/8">
                  <button
                    onClick={() => setSettingsOpen(true)}
                    className="flex items-center gap-1.5 text-[11px] text-slate-400 font-medium hover:text-teal-300 transition-colors"
                  >
                    <Settings className="w-3 h-3" />
                    @ {llmLabel}
                  </button>
                  <span className="text-slate-700">·</span>
                  <span className="text-[11px] text-slate-500">{busy ? 'Working...' : 'Ready'}</span>
                  <div className="flex-1" />
                  <button
                    onClick={() => send(input)}
                    disabled={busy || !input.trim()}
                    className={cn(
                      'w-6 h-6 rounded-full flex items-center justify-center transition-all',
                      input.trim() && !busy
                        ? 'bg-orange-400 hover:bg-orange-300'
                        : 'bg-slate-700 cursor-not-allowed'
                    )}
                  >
                    {busy
                      ? <Loader2 className="w-3 h-3 text-white animate-spin" />
                      : <Send className="w-3 h-3 text-white" />}
                  </button>
                </div>
              </div>
              <div className="hidden sm:flex items-center justify-center gap-4 mt-2">
                <kbd className="text-[10px] text-slate-600 bg-white/5 border border-white/10 rounded px-1.5 py-0.5">⌘K focus</kbd>
                <kbd className="text-[10px] text-slate-600 bg-white/5 border border-white/10 rounded px-1.5 py-0.5">⌘N new chat</kbd>
                <kbd className="text-[10px] text-slate-600 bg-white/5 border border-white/10 rounded px-1.5 py-0.5">⌘/ focus</kbd>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'llmlogs'  && <LlmLogsPanel calls={llmCalls} />}
        {activeTab === 'terminal' && <TerminalPanel logs={containerLogs} />}
        {activeTab === 'files'    && <FilesPanel taskId={activeTaskId} refreshKey={filesRefreshKey} />}

        {(activeTab === 'mcp') && (
          <div className="flex flex-col h-full overflow-y-auto scrollbar-thin p-4 gap-3">
            {/* MCP Connections */}
            <div className="rounded-lg border border-white/8 bg-white/3 overflow-hidden">
              <div className="flex items-center justify-between px-3 py-2.5 border-b border-white/6">
                <div className="flex items-center gap-2">
                  <Plug className="w-3.5 h-3.5 text-teal-400" />
                  <span className="text-xs font-semibold text-slate-200">MCP Log Sources</span>
                  <span className="text-[10px] bg-teal-500/20 text-teal-300 px-1.5 py-0.5 rounded-full">{mcpConns.filter(c=>c.is_active).length} active</span>
                </div>
                <button onClick={() => navigate('/mcp')} className="flex items-center gap-1 text-[10px] text-teal-400 hover:text-teal-300">
                  <ExternalLink className="w-2.5 h-2.5" /> Manage
                </button>
              </div>
              {mcpConns.length === 0 ? (
                <div className="px-3 py-4 text-center">
                  <p className="text-xs text-slate-500">No log sources connected</p>
                  <button onClick={() => navigate('/mcp')} className="mt-2 text-[11px] text-teal-400 hover:text-teal-300 border border-teal-500/30 rounded px-2.5 py-1 hover:bg-teal-500/10 transition-colors">
                    + Add log source
                  </button>
                </div>
              ) : (
                <div className="divide-y divide-white/5">
                  {mcpConns.map(c => (
                    <div key={c.id} className="flex items-center gap-2 px-3 py-2">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${c.is_active ? 'bg-teal-400' : 'bg-slate-600'}`} />
                      <span className="text-[11px] text-slate-300 flex-1 truncate">{c.name}</span>
                      <span className="text-[9px] text-slate-600 font-mono">{c.conn_type}</span>
                      {c.last_test_ok === true && <span className="text-[9px] text-teal-400">✓</span>}
                      {c.last_test_ok === false && <span className="text-[9px] text-red-400">✗</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
            {/* GitHub Repos */}
            <div className="rounded-lg border border-white/8 bg-white/3 overflow-hidden">
              <div className="flex items-center justify-between px-3 py-2.5 border-b border-white/6">
                <div className="flex items-center gap-2">
                  <Github className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-xs font-semibold text-slate-200">Repositories</span>
                  <span className="text-[10px] bg-slate-500/20 text-slate-400 px-1.5 py-0.5 rounded-full">{githubRepos.filter(r=>r.clone_status==='ready').length} ready</span>
                </div>
                <button onClick={() => navigate('/github')} className="flex items-center gap-1 text-[10px] text-teal-400 hover:text-teal-300">
                  <ExternalLink className="w-2.5 h-2.5" /> Manage
                </button>
              </div>
              {githubRepos.length === 0 ? (
                <div className="px-3 py-4 text-center">
                  <p className="text-xs text-slate-500">No repos connected</p>
                  <button onClick={() => navigate('/github')} className="mt-2 text-[11px] text-teal-400 hover:text-teal-300 border border-teal-500/30 rounded px-2.5 py-1 hover:bg-teal-500/10 transition-colors">
                    + Connect repo
                  </button>
                </div>
              ) : (
                <div className="divide-y divide-white/5">
                  {githubRepos.map(r => (
                    <div key={r.id} className="flex items-center gap-2 px-3 py-2">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${
                        r.clone_status === 'ready' ? 'bg-teal-400' :
                        r.clone_status === 'cloning' ? 'bg-blue-400 animate-pulse' :
                        r.clone_status === 'failed' ? 'bg-red-400' : 'bg-slate-600'
                      }`} />
                      <span className="text-[11px] text-slate-300 flex-1 truncate">{r.name}</span>
                      <span className="text-[9px] text-slate-600 font-mono">{r.clone_status ?? '—'}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <p className="text-[10px] text-slate-600 text-center">Active connections are injected as context into every agent run</p>
          </div>
        )}
      </div>

      <LlmSettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSaved={(prov, mdl) => setLlmLabel(`${prov}/${mdl}`)}
      />
    </div>
  )
}
