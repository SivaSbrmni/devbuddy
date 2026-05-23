import { useState, useEffect } from 'react'
import { Link, useLocation, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { useTasks } from '@/hooks/useTasks'
import {
  Menu, Plus, LogOut, Zap, Hash, RefreshCw,
  Play, ChevronRight, Settings,
  MessageSquare, X, LayoutDashboard,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { LlmSettingsModal } from '@/components/LlmSettingsModal'

const STATE_BADGE: Record<string, string> = {
  COMPLETED:      'bg-teal-500/20 text-teal-300 border-teal-500/40',
  DONE:           'bg-teal-500/20 text-teal-300 border-teal-500/40',
  EXECUTING:      'bg-blue-500/20 text-blue-300 border-blue-500/40',
  PLANNING:       'bg-blue-500/20 text-blue-300 border-blue-500/40',
  VALIDATING:     'bg-purple-500/20 text-purple-300 border-purple-500/40',
  SECURITY_REVIEW:'bg-amber-500/20 text-amber-300 border-amber-500/40',
  HUMAN_REVIEW:   'bg-amber-500/20 text-amber-300 border-amber-500/40',
  READY_TO_PUSH:  'bg-teal-500/20 text-teal-300 border-teal-500/40',
  FAILED:         'bg-red-500/20 text-red-300 border-red-500/40',
  QUARANTINED:    'bg-red-500/20 text-red-300 border-red-500/40',
  PENDING:        'bg-slate-500/20 text-slate-300 border-slate-500/40',
  APPROVAL_REQUIRED: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
}

const ALL_SUGGESTIONS = [
  { title: 'Deploy to Test Environment', desc: 'Create a new deploy job in CI/CD pipeline' },
  { title: 'Check SonarQube Quality Gate', desc: 'What is the current quality gate status?' },
  { title: 'Bump Service Snapshot Version', desc: 'From the release branch, bump the version' },
  { title: 'Add rate limiting to auth service', desc: 'Protect login endpoint from brute force' },
  { title: 'Fix memory leak in job processor', desc: 'Identify and patch background worker leak' },
  { title: 'Add OpenTelemetry tracing', desc: 'Instrument all API endpoints with traces' },
]

const BOTTOM_NAV = [
  { id: 'chat',      label: 'Chat',      icon: MessageSquare, path: '/chat' },
  { id: 'tasks',     label: 'Tasks',     icon: Hash,          path: '/tasks' },
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, path: '/dashboard' },
  { id: 'actions',   label: 'Actions',   icon: Zap,           path: '#actions', isDrawer: true },
]

export function Layout() {
  const { user, signOut } = useAuth()
  const { tasks, fetchTasks } = useTasks()
  const location = useLocation()
  const navigate = useNavigate()
  const [sidebarTab, setSidebarTab] = useState<'tasks' | 'actions'>('tasks')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [activeModel, setActiveModel] = useState('')
  const [isMobile, setIsMobile] = useState(false)
  const [suggestionSeed, setSuggestionSeed] = useState(0)

  const suggestions = ALL_SUGGESTIONS.slice(suggestionSeed % 3, (suggestionSeed % 3) + 3)

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)')
    setIsMobile(mq.matches)
    const h = (e: MediaQueryListEvent) => setIsMobile(e.matches)
    mq.addEventListener('change', h)
    return () => mq.removeEventListener('change', h)
  }, [])

  // close drawer on navigation
  useEffect(() => { setDrawerOpen(false) }, [location.pathname])

  const handleSignOut = async () => { await signOut(); navigate('/login') }
  const isChatActive = location.pathname.startsWith('/chat')

  const activeNav = BOTTOM_NAV.find(n => location.pathname.startsWith(n.path.replace('#', '/')) && n.path !== '#actions')?.id ?? 'chat'

  /* ── Shared sidebar content ─────────────────────────────────── */
  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2.5 px-3 py-3 border-b border-white/8 shrink-0">
        {!isMobile && (
          <button
            onClick={() => setSidebarOpen(o => !o)}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/8 transition-colors shrink-0"
          >
            <Menu className="w-4 h-4" />
          </button>
        )}
        {isMobile && (
          <button onClick={() => setDrawerOpen(false)} className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-200 shrink-0">
            <X className="w-4 h-4" />
          </button>
        )}
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded-full bg-teal-500 flex items-center justify-center shrink-0">
            <Play className="w-3.5 h-3.5 text-white fill-white" />
          </div>
          <span className="text-sm font-bold text-white tracking-tight">DevBuddy</span>
        </div>
        <button
          onClick={() => navigate('/chat')}
          className="ml-auto w-8 h-8 rounded-lg bg-teal-600/80 hover:bg-teal-500 flex items-center justify-center transition-colors shrink-0"
          title="New task"
        >
          <Plus className="w-4 h-4 text-white" />
        </button>
      </div>

      {/* Tab pills */}
      <div className="flex items-center gap-1.5 px-3 py-2.5 border-b border-white/8 shrink-0">
        {(['tasks', 'actions'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setSidebarTab(tab)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold transition-colors min-h-[36px]',
              sidebarTab === tab
                ? 'bg-white/10 text-white border border-white/15'
                : 'text-slate-400 hover:text-slate-200'
            )}
          >
            {tab === 'tasks' ? <Hash className="w-3 h-3" /> : <Zap className="w-3 h-3" />}
            {tab === 'tasks' ? 'Tasks' : 'Actions'}
            {tab === 'tasks' && (
              <span className="ml-0.5 bg-teal-500/30 text-teal-300 text-[10px] px-1.5 py-0.5 rounded-full">
                {tasks.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Task list */}
      {sidebarTab === 'tasks' && (
        <div className="flex-1 overflow-y-auto py-2 space-y-0.5 px-2 scrollbar-thin">
          {tasks.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500">No tasks yet</div>
          ) : (
            tasks.map((task, idx) => {
              const num = tasks.length - idx
              const stateLabel = task.state === 'COMPLETED' ? 'DONE' : task.state
              const badgeCls = STATE_BADGE[task.state] ?? STATE_BADGE.PENDING
              const isActive = location.pathname.includes(task.id)
              return (
                <Link
                  key={task.id}
                  to={`/tasks/${task.id}`}
                  className={cn(
                    'group flex flex-col gap-1 px-3 py-3 rounded-lg border-l-2 transition-colors cursor-pointer',
                    isActive
                      ? 'bg-white/8 border-l-teal-400'
                      : 'border-l-transparent hover:bg-white/5 hover:border-l-teal-600'
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-slate-500 font-mono shrink-0">#{num}</span>
                    <span className={cn('text-[10px] font-bold px-1.5 py-0.5 rounded-full border', badgeCls)}>
                      {stateLabel}
                    </span>
                  </div>
                  <p className="text-xs font-bold text-white leading-snug line-clamp-2">{task.title}</p>
                  {task.branch && (
                    <span className="text-[10px] font-mono text-slate-500 truncate">
                      {task.branch}-{task.id.slice(0, 6)}
                    </span>
                  )}
                </Link>
              )
            })
          )}
        </div>
      )}

      {/* Actions tab */}
      {sidebarTab === 'actions' && (
        <div className="flex-1 overflow-y-auto py-2 scrollbar-thin">
          <button
            onClick={() => { setSidebarTab('tasks'); navigate('/chat') }}
            className="w-full flex items-center gap-2 px-4 py-3 text-xs text-teal-400 hover:text-teal-300 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            New task in chat
          </button>
          <div className="mt-1">
            <div className="flex items-center gap-2 px-4 py-1.5">
              <Zap className="w-3 h-3 text-teal-400" />
              <span className="text-[10px] font-bold text-teal-400 uppercase tracking-widest">AI Suggested</span>
              <button
                onClick={() => setSuggestionSeed(s => s + 1)}
                className="ml-auto text-slate-500 hover:text-slate-300 p-1 transition-colors"
                title="Refresh suggestions"
              >
                <RefreshCw className="w-2.5 h-2.5" />
              </button>
            </div>
            <div className="space-y-0.5 px-2">
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => { navigate('/chat') }}
                  className="w-full flex items-start gap-2 px-2 py-3 rounded-lg hover:bg-white/5 transition-colors text-left"
                >
                  <div className="w-7 h-7 rounded bg-teal-500/20 flex items-center justify-center shrink-0 mt-0.5">
                    <Zap className="w-3.5 h-3.5 text-teal-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-slate-200 truncate">{s.title}</p>
                    <p className="text-[10px] text-slate-500 truncate">{s.desc}</p>
                  </div>
                  <Play className="w-3 h-3 text-slate-600 shrink-0 mt-1" />
                </button>
              ))}
            </div>
          </div>
          <div className="mt-3 mx-3 rounded-lg border border-white/10 bg-white/5 p-3">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Automation</p>
            <p className="text-[10px] text-slate-500">Ask in chat to create automations</p>
          </div>
        </div>
      )}

      {/* User footer */}
      <div className="px-3 py-3 border-t border-white/8 flex items-center gap-2 shrink-0">
        <div className="w-7 h-7 rounded-full bg-teal-600 flex items-center justify-center text-[10px] font-bold text-white uppercase shrink-0">
          {user?.email?.charAt(0) ?? 'U'}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[11px] font-medium text-slate-300 truncate">{user?.email}</p>
          <div className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse" />
            <span className="text-[10px] text-teal-400">Live</span>
          </div>
        </div>
        <button onClick={() => setSettingsOpen(true)} className="p-2 rounded-lg text-slate-500 hover:text-teal-400 hover:bg-white/8 transition-colors" title="LLM Settings">
          <Settings className="w-3.5 h-3.5" />
        </button>
        <button onClick={handleSignOut} className="p-2 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-white/8 transition-colors">
          <LogOut className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )

  return (
    <div className="flex h-[100dvh] bg-[#070f1e] overflow-hidden text-slate-100 max-w-[1920px] mx-auto">

      {/* ── DESKTOP SIDEBAR (md+) ──────────────────────────────── */}
      <aside className={cn(
        'hidden md:flex flex-col border-r border-white/8 bg-[#0b1628] transition-all duration-200 shrink-0',
        sidebarOpen ? 'w-72' : 'w-14'
      )}>
        {sidebarOpen ? (
          <SidebarContent />
        ) : (
          /* Collapsed icon rail */
          <div className="flex flex-col items-center gap-1 pt-3">
            <button onClick={() => setSidebarOpen(true)} className="w-10 h-10 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/8">
              <Menu className="w-4 h-4" />
            </button>
            <button onClick={() => navigate('/chat')} className="w-10 h-10 flex items-center justify-center rounded-lg text-teal-400 hover:bg-white/8 mt-2">
              <MessageSquare className="w-4 h-4" />
            </button>
            <button onClick={() => navigate('/tasks')} className="w-10 h-10 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/8">
              <Hash className="w-4 h-4" />
            </button>
            <button onClick={() => navigate('/dashboard')} className="w-10 h-10 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/8">
              <LayoutDashboard className="w-4 h-4" />
            </button>
            <div className="flex-1" />
            <button onClick={handleSignOut} className="w-10 h-10 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/8 mb-3">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </aside>

      {/* ── MOBILE DRAWER OVERLAY ──────────────────────────────── */}
      {isMobile && drawerOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setDrawerOpen(false)} />
          <aside className="relative w-[85vw] max-w-[320px] bg-[#0b1628] flex flex-col h-full shadow-2xl border-r border-white/8 z-10">
            <SidebarContent />
          </aside>
        </div>
      )}

      <LlmSettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSaved={(prov, mdl) => setActiveModel(`${prov}/${mdl}`)}
      />

      {/* ── MAIN CONTENT ───────────────────────────────────────── */}
      <main className="flex-1 overflow-hidden flex flex-col min-w-0">
        {/* Mobile top bar */}
        <div className="flex md:hidden items-center gap-3 px-4 py-3 border-b border-white/8 bg-[#0b1628] shrink-0">
          <button
            onClick={() => setDrawerOpen(true)}
            className="w-9 h-9 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/8"
          >
            <Menu className="w-4.5 h-4.5" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-teal-500 flex items-center justify-center">
              <Play className="w-3 h-3 text-white fill-white" />
            </div>
            <span className="text-sm font-bold text-white">DevBuddy</span>
          </div>
          <div className="flex-1" />
          <button onClick={() => navigate('/chat')} className="w-9 h-9 rounded-lg bg-teal-600/80 hover:bg-teal-500 flex items-center justify-center">
            <Plus className="w-4 h-4 text-white" />
          </button>
        </div>

        {/* Desktop page title bar (non-chat pages) */}
        {!isChatActive && (
          <div className="hidden md:flex items-center gap-3 px-5 py-3 border-b border-white/8 bg-[#0b1628] shrink-0">
            <ChevronRight className="w-3 h-3 text-slate-500" />
            <span className="text-xs text-slate-400 font-medium capitalize">
              {location.pathname.replace('/', '')}
            </span>
            <button onClick={() => fetchTasks()} className="ml-auto p-1.5 rounded text-slate-500 hover:text-slate-300 transition-colors">
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Page content */}
        <div className="flex-1 overflow-hidden">
          <Outlet />
        </div>

        {/* ── MOBILE BOTTOM NAV ────────────────────────────────── */}
        <nav className="flex md:hidden items-center border-t border-white/8 bg-[#0b1628] shrink-0 safe-bottom">
          {BOTTOM_NAV.map(item => {
            const isActive = activeNav === item.id
            return (
              <button
                key={item.id}
                onClick={() => {
                  if ('isDrawer' in item && item.isDrawer) {
                    setSidebarTab('actions')
                    setDrawerOpen(true)
                  } else {
                    navigate(item.path)
                  }
                }}
                className={cn(
                  'flex-1 flex flex-col items-center justify-center gap-1 py-3 min-h-[56px] transition-colors',
                  isActive ? 'text-teal-400' : 'text-slate-500'
                )}
              >
                <item.icon className={cn('w-5 h-5', isActive && 'text-teal-400')} />
                <span className="text-[10px] font-medium">{item.label}</span>
              </button>
            )
          })}
        </nav>
      </main>
    </div>
  )
}
