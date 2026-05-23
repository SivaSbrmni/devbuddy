import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ShieldCheck, RefreshCw, Search } from 'lucide-react'

interface AuditLog {
  id: string
  tenant_id: string
  task_id?: string
  event_type: string
  actor_type: string
  actor_id: string
  resource_type?: string
  resource_id?: string
  action: string
  outcome: string
  details: Record<string, unknown>
  trace_id?: string
  created_at: string
}

export function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const fetchLogs = async () => {
    setLoading(true)
    try {
      const data = await api.get<AuditLog[]>('/api/v1/audit?limit=100')
      setLogs(data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchLogs() }, [])

  const filtered = logs.filter(l =>
    !search || l.event_type.toLowerCase().includes(search.toLowerCase()) ||
    l.actor_id.toLowerCase().includes(search.toLowerCase()) ||
    l.action.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShieldCheck className="w-6 h-6 text-primary" />
          <div>
            <h1 className="text-2xl font-bold text-foreground">Audit Log</h1>
            <p className="text-sm text-muted-foreground">Immutable append-only audit trail</p>
          </div>
        </div>
        <Button variant="ghost" size="icon" onClick={fetchLogs}>
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      <div className="flex items-center gap-3 rounded-lg border border-input bg-background px-3">
        <Search className="w-4 h-4 text-muted-foreground shrink-0" />
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search by event type, actor, or action..."
          className="flex-1 py-2.5 text-sm bg-transparent text-foreground placeholder:text-muted-foreground focus:outline-none"
        />
      </div>

      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="grid grid-cols-12 gap-4 px-4 py-3 border-b border-border bg-secondary/30 text-xs font-medium text-muted-foreground uppercase tracking-wide">
          <div className="col-span-2">Time</div>
          <div className="col-span-2">Event Type</div>
          <div className="col-span-2">Actor</div>
          <div className="col-span-2">Action</div>
          <div className="col-span-2">Resource</div>
          <div className="col-span-1">Outcome</div>
          <div className="col-span-1">Trace</div>
        </div>
        <div className="divide-y divide-border max-h-[60vh] overflow-y-auto scrollbar-thin">
          {loading ? (
            <div className="p-8 text-center text-muted-foreground">Loading audit logs...</div>
          ) : filtered.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">No audit logs found</div>
          ) : (
            filtered.map(log => (
              <div key={log.id} className="grid grid-cols-12 gap-4 px-4 py-3 text-xs hover:bg-accent/30 transition-colors">
                <div className="col-span-2 text-muted-foreground">{formatDate(log.created_at)}</div>
                <div className="col-span-2 font-medium text-foreground truncate">{log.event_type}</div>
                <div className="col-span-2 text-muted-foreground truncate">
                  <span className="text-foreground">{log.actor_type}</span>
                  <span className="ml-1 opacity-60">{log.actor_id.slice(0, 8)}…</span>
                </div>
                <div className="col-span-2 text-foreground truncate">{log.action}</div>
                <div className="col-span-2 text-muted-foreground truncate">
                  {log.resource_type && <span>{log.resource_type}</span>}
                  {log.resource_id && <span className="ml-1 opacity-60">{log.resource_id.slice(0, 8)}…</span>}
                </div>
                <div className="col-span-1">
                  <Badge variant={log.outcome === 'success' ? 'success' : 'destructive'} className="text-[10px] px-1.5">
                    {log.outcome}
                  </Badge>
                </div>
                <div className="col-span-1 text-muted-foreground font-mono truncate">
                  {log.trace_id ? log.trace_id.slice(0, 8) : '—'}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
      <p className="text-xs text-muted-foreground text-right">
        Showing {filtered.length} of {logs.length} entries · SHA-256 signed
      </p>
    </div>
  )
}
