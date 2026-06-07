import { useEffect, useState } from 'react'
import { getDashboard, healthCheck, listProjects } from '../api/client'

export default function DashboardPage() {
  const [health, setHealth] = useState<any>(null)
  const [projects, setProjects] = useState<any[]>([])
  const [metrics, setMetrics] = useState<any>(null)

  useEffect(() => {
    healthCheck().then(setHealth).catch(() => setHealth({ status: 'unreachable' }))
    listProjects().then(setProjects).catch(() => {})
    getDashboard().then(setMetrics).catch(() => {})
  }, [])

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>Dashboard</h2>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 16, marginBottom: 32 }}>
        <div className="card">
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>System Status</p>
          <p style={{ fontSize: 20, fontWeight: 600, color: health?.status === 'healthy' ? 'var(--success)' : 'var(--error)', marginTop: 8 }}>
            {health?.status ?? 'Loading...'}
          </p>
        </div>
        <div className="card">
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Active Projects</p>
          <p style={{ fontSize: 20, fontWeight: 600, marginTop: 8 }}>{projects.length}</p>
        </div>
        <div className="card">
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Total Runs</p>
          <p style={{ fontSize: 20, fontWeight: 600, marginTop: 8 }}>
            {metrics?.runs?.breakdown
              ? Object.values(metrics.runs.breakdown as Record<string, Record<string, number>>).reduce(
                  (sum: number, statuses) => sum + Object.values(statuses).reduce((a: number, b: number) => a + b, 0), 0
                )
              : 0}
          </p>
        </div>
      </div>

      {metrics?.runs?.success_rates && (
        <div className="card" style={{ marginBottom: 24 }}>
          <h3 style={{ marginBottom: 16 }}>Success Rates</h3>
          <div style={{ display: 'flex', gap: 24 }}>
            {Object.entries(metrics.runs.success_rates as Record<string, number>).map(([type, rate]) => (
              <div key={type}>
                <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>{type}</p>
                <p style={{ fontSize: 18, fontWeight: 600, color: rate > 80 ? 'var(--success)' : rate > 50 ? 'var(--warning)' : 'var(--error)' }}>
                  {rate.toFixed(1)}%
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {metrics?.tokens && Object.keys(metrics.tokens).length > 0 && (
        <div className="card">
          <h3 style={{ marginBottom: 16 }}>Token Usage</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={{ textAlign: 'left', padding: 8, color: 'var(--text-muted)', fontSize: 13 }}>Provider</th>
                <th style={{ textAlign: 'right', padding: 8, color: 'var(--text-muted)', fontSize: 13 }}>Input Tokens</th>
                <th style={{ textAlign: 'right', padding: 8, color: 'var(--text-muted)', fontSize: 13 }}>Output Tokens</th>
                <th style={{ textAlign: 'right', padding: 8, color: 'var(--text-muted)', fontSize: 13 }}>Cost (USD)</th>
                <th style={{ textAlign: 'right', padding: 8, color: 'var(--text-muted)', fontSize: 13 }}>Avg Latency</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(metrics.tokens as Record<string, any>).map(([provider, data]) => (
                <tr key={provider} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: 8 }}>{provider}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{data.input_tokens?.toLocaleString()}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{data.output_tokens?.toLocaleString()}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>${data.total_cost_usd?.toFixed(4)}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{data.avg_latency_ms?.toFixed(0)}ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
