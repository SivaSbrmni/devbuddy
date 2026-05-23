import { Link, useLocation, Outlet } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import {
  LayoutDashboard, ListTodo, ShieldCheck, ScrollText, Activity,
  LogOut, Bot, ChevronRight
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/tasks', label: 'Tasks', icon: ListTodo },
  { to: '/audit', label: 'Audit Log', icon: ShieldCheck },
  { to: '/logs', label: 'Log Explorer', icon: ScrollText },
]

export function Layout() {
  const { user, signOut } = useAuth()
  const location = useLocation()

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 flex flex-col border-r border-border bg-card">
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-5 py-4 border-b border-border">
          <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
            <Bot className="w-5 h-5 text-primary" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">DevBuddy</p>
            <p className="text-xs text-muted-foreground">Enterprise Agent Platform</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-3 space-y-1">
          {navItems.map(({ to, label, icon: Icon }) => {
            const active = location.pathname.startsWith(to)
            return (
              <Link
                key={to}
                to={to}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors',
                  active
                    ? 'bg-primary/15 text-primary font-medium'
                    : 'text-muted-foreground hover:bg-accent hover:text-foreground'
                )}
              >
                <Icon className="w-4 h-4 shrink-0" />
                {label}
                {active && <ChevronRight className="w-3 h-3 ml-auto" />}
              </Link>
            )
          })}
        </nav>

        {/* User */}
        <div className="p-3 border-t border-border">
          <div className="flex items-center gap-3 px-2 py-2">
            <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center text-xs font-semibold text-primary uppercase shrink-0">
              {user?.email?.charAt(0) ?? 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-foreground truncate">{user?.email}</p>
              <div className="flex items-center gap-1 mt-0.5">
                <Activity className="w-2.5 h-2.5 text-emerald-400" />
                <span className="text-[10px] text-emerald-400">Active</span>
              </div>
            </div>
            <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={signOut}>
              <LogOut className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
