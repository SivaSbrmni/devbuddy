import { useEffect, useState } from 'react'
import { getDashboard } from '../api/client'

export default function MetricsPage() {
  const [metrics, setMetrics] = useState<any>(null)

  useEffect(() => { getDashboard().then(setMetrics).catch(() => {}) }, [])

  if (!metrics) return <p style={{ color: 'var(--text-muted)' }}>Loading metrics...</p>

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>Observability Dashboard</h2>

      {/* Run breakdown */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h3 style={{ marginBottom: 16 }}>Run Breakdown</h3>
        {metrics.runs?.breakdown && Object.keys(metrics.runs.breakdown).length > 0 ? (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={{ textAlign: 'left', padding: 8, color: 'var(--text-muted)', fontSize: 13 }}>Type</th>
                <th style={{ textAlign: 'right', padding: 8, color: 'var(--text-muted)', fontSize: 13 }}>Success</th>
                <th style={{ textAlign: 'right', padding: 8, color: 'var(--text-muted)', fontSize: 13 }}>Failed</th>
                <th style={{ textAlign: 'right', padding: 8, color: 'var(--text-muted)', fontSize: 13 }}>Rate</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(metrics.runs.breakdown as Record<string, Record<string, number>>).map(([type, statuses]) => (
                <tr key={type} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: 8 }}>{type}</td>
                  <td style={{ padding: 8, textAlign: 'right', color: 'var(--success)' }}>{statuses.success || 0}</td>
                  <td style={{ padding: 8, textAlign: 'right', color: 'var(--error)' }}>{statuses.failed || 0}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>
                    {metrics.runs.success_rates?.[type]?.toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p style={{ color: 'var(--text-muted)' }}>No run data yet.</p>
        )}
      </div>

      {/* Token usage */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h3 style={{ marginBottom: 16 }}>Token Usage by Provider</h3>
        {metrics.tokens && Object.keys(metrics.tokens).length > 0 ? (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={{ textAlign: 'left', padding: 8, color: 'var(--text-muted)', fontSize: 13 }}>Provider</th>
                <th style={{ textAlign: 'right', padding: 8, color: 'var(--text-muted)', fontSize: 13 }}>Input</th>
                <th style={{ textAlign: 'right', padding: 8, color: 'var(--text-muted)', fontSize: 13 }}>Output</th>
                <th style={{ textAlign: 'right', padding: 8, color: 'var(--text-muted)', fontSize: 13 }}>Cost</th>
                <th style={{ textAlign: 'right', padding: 8, color: 'var(--text-muted)', fontSize: 13 }}>Latency</th>
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
        ) : (
          <p style={{ color: 'var(--text-muted)' }}>No token usage data yet.</p>
        )}
      </div>

      {/* Deployments */}
      <div className="card">
        <h3 style={{ marginBottom: 16 }}>Deployment History</h3>
        {metrics.deployments && Object.keys(metrics.deployments).length > 0 ? (
          <div style={{ display: 'flex', gap: 24 }}>
            {Object.entries(metrics.deployments as Record<string, Record<string, number>>).map(([provider, statuses]) => (
              <div key={provider}>
                <p style={{ fontWeight: 600, marginBottom: 8 }}>{provider}</p>
                {Object.entries(statuses).map(([status, count]) => (
                  <p key={status} style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                    {status}: {count}
                  </p>
                ))}
              </div>
            ))}
          </div>
        ) : (
          <p style={{ color: 'var(--text-muted)' }}>No deployment data yet.</p>
        )}
      </div>
    </div>
  )
}
