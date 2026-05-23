import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTasks } from '@/hooks/useTasks'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { timeAgo } from '@/lib/utils'
import { Plus, GitBranch, Clock, ChevronRight, RefreshCw, X } from 'lucide-react'

const STATE_COLORS: Record<string, 'success' | 'destructive' | 'warning' | 'info' | 'purple' | 'secondary'> = {
  COMPLETED: 'success', FAILED: 'destructive', QUARANTINED: 'destructive',
  EXECUTING: 'info', VALIDATING: 'purple', SECURITY_REVIEW: 'warning',
  HUMAN_REVIEW: 'warning', PLANNING: 'info', PENDING: 'secondary',
  APPROVAL_REQUIRED: 'warning', READY_TO_PUSH: 'success',
}

export function TasksPage() {
  const { tasks, loading, fetchTasks, createTask } = useTasks()
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState({ title: '', description: '', repo_id: '', branch: '', policy_profile: 'standard' })
  const [error, setError] = useState<string | null>(null)

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.title.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      await createTask({ ...form, branch: form.branch || undefined, repo_id: form.repo_id || undefined })
      setForm({ title: '', description: '', repo_id: '', branch: '', policy_profile: 'standard' })
      setShowForm(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create task')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Tasks</h1>
          <p className="text-muted-foreground mt-1">Manage autonomous agent tasks</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={fetchTasks}>
            <RefreshCw className="w-4 h-4" />
          </Button>
          <Button onClick={() => setShowForm(true)} className="gap-2">
            <Plus className="w-4 h-4" />
            New Task
          </Button>
        </div>
      </div>

      {/* Create Form */}
      {showForm && (
        <div className="rounded-xl border border-primary/30 bg-card p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-foreground">Create New Task</h2>
            <Button variant="ghost" size="icon" onClick={() => setShowForm(false)}>
              <X className="w-4 h-4" />
            </Button>
          </div>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 gap-4">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">Task Title *</label>
                <input
                  type="text"
                  value={form.title}
                  onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                  placeholder="e.g. Add rate limiting middleware to auth service"
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">Description</label>
                <textarea
                  value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="Detailed task description..."
                  rows={3}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1.5">Repository ID</label>
                  <input
                    type="text"
                    value={form.repo_id}
                    onChange={e => setForm(f => ({ ...f, repo_id: e.target.value }))}
                    placeholder="org/repo-name"
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1.5">Branch</label>
                  <input
                    type="text"
                    value={form.branch}
                    onChange={e => setForm(f => ({ ...f, branch: e.target.value }))}
                    placeholder="feature/my-branch"
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">Policy Profile</label>
                <select
                  value={form.policy_profile}
                  onChange={e => setForm(f => ({ ...f, policy_profile: e.target.value }))}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="standard">Standard</option>
                  <option value="strict">Strict</option>
                  <option value="permissive">Permissive (Dev Only)</option>
                </select>
              </div>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button type="submit" disabled={submitting}>
                {submitting ? 'Creating...' : 'Create Task'}
              </Button>
            </div>
          </form>
        </div>
      )}

      {/* Task List */}
      <div className="rounded-xl border border-border bg-card divide-y divide-border">
        {loading ? (
          <div className="p-8 text-center text-muted-foreground">Loading tasks...</div>
        ) : tasks.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-muted-foreground">No tasks yet.</p>
            <Button className="mt-3 gap-2" onClick={() => setShowForm(true)}>
              <Plus className="w-4 h-4" /> Create your first task
            </Button>
          </div>
        ) : (
          tasks.map(task => (
            <Link key={task.id} to={`/tasks/${task.id}`} className="flex items-center gap-4 p-4 hover:bg-accent/40 transition-colors">
              <div className="flex-1 min-w-0 space-y-1">
                <p className="text-sm font-medium text-foreground truncate">{task.title}</p>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  {task.repo_id && (
                    <span className="flex items-center gap-1">
                      <GitBranch className="w-3 h-3" />
                      {task.repo_id}{task.branch ? `/${task.branch}` : ''}
                    </span>
                  )}
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {timeAgo(task.updated_at)}
                  </span>
                  <span>Iter: {task.iteration_count}</span>
                </div>
              </div>
              <Badge variant={STATE_COLORS[task.state] ?? 'secondary'}>{task.state}</Badge>
              <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0" />
            </Link>
          ))
        )}
      </div>
    </div>
  )
}
