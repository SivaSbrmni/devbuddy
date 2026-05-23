import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { useTasks, Task } from '@/hooks/useTasks'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { timeAgo } from '@/lib/utils'
import {
  ListTodo, CheckCircle2, XCircle, Clock, Zap,
  AlertTriangle, ArrowRight, TrendingUp, Activity
} from 'lucide-react'

const STATE_COLORS: Record<string, 'success' | 'destructive' | 'warning' | 'info' | 'purple' | 'secondary'> = {
  COMPLETED: 'success',
  FAILED: 'destructive',
  QUARANTINED: 'destructive',
  EXECUTING: 'info',
  VALIDATING: 'purple',
  SECURITY_REVIEW: 'warning',
  HUMAN_REVIEW: 'warning',
  PLANNING: 'info',
  PENDING: 'secondary',
  APPROVAL_REQUIRED: 'warning',
  READY_TO_PUSH: 'success',
}

export function DashboardPage() {
  const { user } = useAuth()
  const { tasks, loading } = useTasks()
  const [health, setHealth] = useState<{ status: string; error_count_last_hour: number } | null>(null)

  useEffect(() => {
    api.get<{ status: string; error_count_last_hour: number }>('/api/v1/logs/health')
      .then(setHealth)
      .catch(() => null)
  }, [])

  const stats = {
    total: tasks.length,
    active: tasks.filter(t => !['COMPLETED', 'FAILED', 'QUARANTINED'].includes(t.state)).length,
    completed: tasks.filter(t => t.state === 'COMPLETED').length,
    failed: tasks.filter(t => ['FAILED', 'QUARANTINED'].includes(t.state)).length,
  }

  const recent = tasks.slice(0, 6)

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
        <p className="text-muted-foreground mt-1">
          Welcome back, {user?.email?.split('@')[0]}. Platform status overview.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Tasks', value: stats.total, icon: ListTodo, color: 'text-blue-400' },
          { label: 'Active', value: stats.active, icon: Zap, color: 'text-amber-400' },
          { label: 'Completed', value: stats.completed, icon: CheckCircle2, color: 'text-emerald-400' },
          { label: 'Failed', value: stats.failed, icon: XCircle, color: 'text-red-400' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="rounded-xl border border-border bg-card p-5 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">{label}</p>
              <Icon className={`w-4 h-4 ${color}`} />
            </div>
            <p className="text-3xl font-bold text-foreground">{loading ? '—' : value}</p>
          </div>
        ))}
      </div>

      {/* System Health */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-primary" />
            <h2 className="font-semibold text-foreground">System Health</h2>
          </div>
          <Link to="/logs">
            <Button variant="ghost" size="sm" className="gap-1 text-xs">
              View logs <ArrowRight className="w-3 h-3" />
            </Button>
          </Link>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'API', status: 'Operational', ok: true },
            { label: 'Database', status: 'Operational', ok: true },
            { label: 'Log Pipeline', status: health ? health.status : 'Checking...', ok: health?.status === 'healthy' },
            { label: 'Errors (1h)', status: health ? String(health.error_count_last_hour) : '—', ok: (health?.error_count_last_hour ?? 0) < 10 },
          ].map(({ label, status, ok }) => (
            <div key={label} className="flex items-center gap-3 p-3 rounded-lg bg-secondary/50">
              <div className={`w-2 h-2 rounded-full shrink-0 ${ok ? 'bg-emerald-400' : 'bg-amber-400'}`} />
              <div>
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="text-sm font-medium text-foreground">{status}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Tasks */}
      <div className="rounded-xl border border-border bg-card">
        <div className="flex items-center justify-between p-5 border-b border-border">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-primary" />
            <h2 className="font-semibold text-foreground">Recent Tasks</h2>
          </div>
          <Link to="/tasks">
            <Button variant="ghost" size="sm" className="gap-1 text-xs">
              View all <ArrowRight className="w-3 h-3" />
            </Button>
          </Link>
        </div>
        <div className="divide-y divide-border">
          {loading ? (
            <div className="p-8 text-center text-muted-foreground">Loading...</div>
          ) : recent.length === 0 ? (
            <div className="p-8 text-center">
              <AlertTriangle className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No tasks yet. Create your first task.</p>
              <Link to="/tasks">
                <Button size="sm" className="mt-3">Create Task</Button>
              </Link>
            </div>
          ) : (
            recent.map((task: Task) => (
              <Link key={task.id} to={`/tasks/${task.id}`} className="flex items-center gap-4 p-4 hover:bg-accent/50 transition-colors">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{task.title}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {task.repo_id && <span className="mr-2">{task.repo_id}</span>}
                    <Clock className="w-3 h-3 inline mr-1" />
                    {timeAgo(task.updated_at)}
                  </p>
                </div>
                <Badge variant={STATE_COLORS[task.state] ?? 'secondary'}>{task.state}</Badge>
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
