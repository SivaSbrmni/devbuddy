import { useState } from 'react'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollText, Search, RefreshCw, AlertCircle } from 'lucide-react'

interface LogEntry {
  timestamp: string
  labels: Record<string, string>
  line: string
}

interface LogResponse {
  logs: LogEntry[]
  count: number
}

const SERVICES = ['backend', 'frontend', 'postgres', 'loki']
const LEVELS = ['ERROR', 'WARNING', 'INFO', 'DEBUG']

export function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [form, setForm] = useState({
    service: '', level: '', search: '', last_minutes: '60', limit: '200'
  })

  const fetchLogs = async () => {
    setLoading(true)
    setSearched(true)
    try {
      const params = new URLSearchParams()
      if (form.service) params.set('service', form.service)
      if (form.level) params.set('level', form.level)
      if (form.search) params.set('search', form.search)
      params.set('last_minutes', form.last_minutes)
      params.set('limit', form.limit)
      const data = await api.get<LogResponse>(`/api/v1/logs?${params}`)
      setLogs(data.logs)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const parseLine = (line: string): { level?: string; message?: string; rest: string } => {
    try {
      const obj = JSON.parse(line)
      return { level: obj.level, message: obj.event || obj.message, rest: line }
    } catch {
      return { rest: line }
    }
  }

  const levelColor = (level?: string) => {
    switch (level?.toUpperCase()) {
      case 'ERROR': case 'CRITICAL': return 'destructive'
      case 'WARNING': case 'WARN': return 'warning'
      case 'INFO': return 'info'
      case 'DEBUG': return 'secondary'
      default: return 'secondary'
    }
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <ScrollText className="w-6 h-6 text-primary" />
        <div>
          <h1 className="text-2xl font-bold text-foreground">Log Explorer</h1>
          <p className="text-sm text-muted-foreground">Query platform logs via Loki</p>
        </div>
      </div>

      {/* Query Controls */}
      <div className="rounded-xl border border-border bg-card p-5 space-y-4">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Service</label>
            <select
              value={form.service}
              onChange={e => setForm(f => ({ ...f, service: e.target.value }))}
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">All Services</option>
              {SERVICES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Level</label>
            <select
              value={form.level}
              onChange={e => setForm(f => ({ ...f, level: e.target.value }))}
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">All Levels</option>
              {LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Time Range</label>
            <select
              value={form.last_minutes}
              onChange={e => setForm(f => ({ ...f, last_minutes: e.target.value }))}
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="15">Last 15 min</option>
              <option value="60">Last 1 hour</option>
              <option value="360">Last 6 hours</option>
              <option value="1440">Last 24 hours</option>
              <option value="10080">Last 7 days</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Limit</label>
            <select
              value={form.limit}
              onChange={e => setForm(f => ({ ...f, limit: e.target.value }))}
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="50">50</option>
              <option value="200">200</option>
              <option value="500">500</option>
            </select>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex-1 flex items-center gap-2 rounded-lg border border-input bg-background px-3">
            <Search className="w-4 h-4 text-muted-foreground shrink-0" />
            <input
              type="text"
              value={form.search}
              onChange={e => setForm(f => ({ ...f, search: e.target.value }))}
              onKeyDown={e => e.key === 'Enter' && fetchLogs()}
              placeholder="Search log text..."
              className="flex-1 py-2.5 text-sm bg-transparent text-foreground placeholder:text-muted-foreground focus:outline-none"
            />
          </div>
          <Button onClick={fetchLogs} disabled={loading} className="gap-2">
            {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            Query
          </Button>
        </div>
      </div>

      {/* Results */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-secondary/20">
          <span className="text-sm font-medium text-foreground">
            {searched ? `${logs.length} results` : 'Enter a query above'}
          </span>
          <span className="text-xs text-muted-foreground">Source: Loki</span>
        </div>
        <div className="max-h-[55vh] overflow-y-auto scrollbar-thin font-mono text-xs">
          {!searched ? (
            <div className="p-12 text-center">
              <AlertCircle className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-muted-foreground">Select filters and click Query to load logs</p>
            </div>
          ) : logs.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">No logs found for this query</div>
          ) : (
            logs.map((log, i) => {
              const parsed = parseLine(log.line)
              const ts = new Date(parseInt(log.timestamp) / 1e6).toISOString()
              return (
                <div key={i} className="flex gap-3 px-4 py-1.5 border-b border-border/50 hover:bg-accent/20 transition-colors">
                  <span className="text-muted-foreground shrink-0 w-48">{ts.replace('T', ' ').slice(0, 19)}</span>
                  {parsed.level && (
                    <Badge variant={levelColor(parsed.level) as 'success'|'destructive'|'warning'|'info'|'secondary'} className="shrink-0 text-[10px] px-1.5 h-4 self-center">
                      {parsed.level.toUpperCase()}
                    </Badge>
                  )}
                  {log.labels.service && (
                    <span className="text-purple-400 shrink-0">[{log.labels.service}]</span>
                  )}
                  <span className="text-foreground break-all">{parsed.message || log.line}</span>
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
