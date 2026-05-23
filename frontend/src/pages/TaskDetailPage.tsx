import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useTask } from '@/hooks/useTasks'
import { useTaskStream } from '@/hooks/useWebSocket'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { formatDate, timeAgo } from '@/lib/utils'
import { ArrowLeft, Wifi, WifiOff, ChevronRight, RefreshCw } from 'lucide-react'

const STATES = [
  'PENDING','PLANNING','APPROVAL_REQUIRED','EXECUTING',
  'VALIDATING','SECURITY_REVIEW','HUMAN_REVIEW','READY_TO_PUSH','COMPLETED'
]
const STATE_COLORS: Record<string, 'success'|'destructive'|'warning'|'info'|'purple'|'secondary'> = {
  COMPLETED:'success', FAILED:'destructive', QUARANTINED:'destructive',
  EXECUTING:'info', VALIDATING:'purple', SECURITY_REVIEW:'warning',
  HUMAN_REVIEW:'warning', PLANNING:'info', PENDING:'secondary',
  APPROVAL_REQUIRED:'warning', READY_TO_PUSH:'success',
}
const NEXT_STATES: Record<string, string[]> = {
  PENDING:['PLANNING','FAILED'],
  PLANNING:['EXECUTING','APPROVAL_REQUIRED','FAILED'],
  APPROVAL_REQUIRED:['EXECUTING','FAILED'],
  EXECUTING:['VALIDATING','FAILED','QUARANTINED'],
  VALIDATING:['SECURITY_REVIEW','READY_TO_PUSH','FAILED'],
  SECURITY_REVIEW:['HUMAN_REVIEW','READY_TO_PUSH','QUARANTINED'],
  HUMAN_REVIEW:['READY_TO_PUSH','FAILED'],
  READY_TO_PUSH:['COMPLETED','FAILED'],
}

export function TaskDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { task, loading, error, setTask } = useTask(id)
  const { events, connected } = useTaskStream(id)
  const [transitioning, setTransitioning] = useState(false)

  const handleTransition = async (toState: string) => {
    if (!id || !task) return
    setTransitioning(true)
    try {
      const updated = await api.patch<typeof task>(`/api/v1/tasks/${id}/state`, { to_state: toState })
      setTask(updated)
    } catch (e) {
      console.error(e)
    } finally {
      setTransitioning(false)
    }
  }

  if (loading) return <div className="p-8 text-muted-foreground">Loading...</div>
  if (error || !task) return <div className="p-8 text-destructive">{error || 'Task not found'}</div>

  const nextStates = NEXT_STATES[task.state] ?? []
  const stateIndex = STATES.indexOf(task.state)

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Link to="/tasks">
          <Button variant="ghost" size="icon" className="mt-0.5">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-bold text-foreground">{task.title}</h1>
            <Badge variant={STATE_COLORS[task.state] ?? 'secondary'}>{task.state}</Badge>
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              {connected ? <Wifi className="w-3 h-3 text-emerald-400" /> : <WifiOff className="w-3 h-3 text-muted-foreground" />}
              {connected ? 'Live' : 'Offline'}
            </div>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            {task.repo_id && <span className="mr-3">{task.repo_id}{task.branch ? `@${task.branch}` : ''}</span>}
            Updated {timeAgo(task.updated_at)} · Iterations: {task.iteration_count}
          </p>
        </div>
      </div>

      {/* State Machine */}
      <div className="rounded-xl border border-border bg-card p-5 space-y-4">
        <h2 className="text-sm font-semibold text-foreground">Agent State Machine</h2>
        <div className="flex items-center gap-1 flex-wrap">
          {STATES.map((s, i) => (
            <div key={s} className="flex items-center gap-1">
              <div className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                s === task.state
                  ? 'bg-primary text-primary-foreground'
                  : i < stateIndex
                  ? 'bg-emerald-500/20 text-emerald-400'
                  : 'bg-secondary text-muted-foreground'
              }`}>
                {s.replace(/_/g, ' ')}
              </div>
              {i < STATES.length - 1 && <ChevronRight className="w-3 h-3 text-muted-foreground" />}
            </div>
          ))}
        </div>
        {['FAILED','QUARANTINED'].includes(task.state) && (
          <div className="px-3 py-2 rounded-lg bg-destructive/10 border border-destructive/20">
            <p className="text-xs font-medium text-destructive">
              Task is in terminal state: {task.state}
            </p>
          </div>
        )}
        {nextStates.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap pt-1">
            <span className="text-xs text-muted-foreground">Transition to:</span>
            {nextStates.map(s => (
              <Button
                key={s}
                size="sm"
                variant={s === 'FAILED' || s === 'QUARANTINED' ? 'destructive' : 'outline'}
                onClick={() => handleTransition(s)}
                disabled={transitioning}
                className="h-7 text-xs"
              >
                {transitioning ? <RefreshCw className="w-3 h-3 animate-spin" /> : s.replace(/_/g, ' ')}
              </Button>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Live Event Stream */}
        <div className="rounded-xl border border-border bg-card p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">Live Event Stream</h2>
            <span className="text-xs text-muted-foreground">{events.length} events</span>
          </div>
          <div className="space-y-1.5 max-h-64 overflow-y-auto scrollbar-thin">
            {events.length === 0 ? (
              <p className="text-xs text-muted-foreground py-4 text-center">Waiting for events...</p>
            ) : (
              [...events].reverse().map((ev, i) => (
                <div key={i} className="text-xs rounded-lg bg-secondary/50 px-3 py-2 font-mono">
                  <span className="text-muted-foreground">{new Date(ev.timestamp).toLocaleTimeString()} </span>
                  <span className="text-primary">{ev.event.type as string}</span>
                  {ev.event.state != null && <span className="text-emerald-400"> → {String(ev.event.state)}</span>}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Task Events History */}
        <div className="rounded-xl border border-border bg-card p-5 space-y-3">
          <h2 className="text-sm font-semibold text-foreground">Event History</h2>
          <div className="space-y-1.5 max-h-64 overflow-y-auto scrollbar-thin">
            {!task.events || task.events.length === 0 ? (
              <p className="text-xs text-muted-foreground py-4 text-center">No events yet</p>
            ) : (
              [...task.events].reverse().map(ev => (
                <div key={ev.id} className="text-xs rounded-lg bg-secondary/50 px-3 py-2">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-foreground">{ev.event_type}</span>
                    <span className="text-muted-foreground">{timeAgo(ev.created_at)}</span>
                  </div>
                  {ev.from_state && (
                    <div className="text-muted-foreground mt-0.5">
                      {ev.from_state} → {ev.to_state}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Task Details */}
      <div className="rounded-xl border border-border bg-card p-5">
        <h2 className="text-sm font-semibold text-foreground mb-4">Task Details</h2>
        <dl className="grid grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
          {[
            { label: 'Task ID', value: task.id.slice(0, 8) + '...' },
            { label: 'Policy Profile', value: task.policy_profile },
            { label: 'Created', value: formatDate(task.created_at) },
            { label: 'Last Updated', value: formatDate(task.updated_at) },
            { label: 'Iterations', value: String(task.iteration_count) },
            { label: 'Tokens Used', value: String(task.token_budget_used) },
          ].map(({ label, value }) => (
            <div key={label}>
              <dt className="text-xs text-muted-foreground">{label}</dt>
              <dd className="mt-0.5 font-medium text-foreground truncate">{value}</dd>
            </div>
          ))}
        </dl>
        {task.description && (
          <div className="mt-4 pt-4 border-t border-border">
            <p className="text-xs text-muted-foreground mb-1">Description</p>
            <p className="text-sm text-foreground">{task.description}</p>
          </div>
        )}
      </div>
    </div>
  )
}
