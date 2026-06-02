import { Link, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'

const NAV_ITEMS = [
  { path: '/', label: 'Dashboard' },
  { path: '/projects', label: 'Projects' },
  { path: '/workspace', label: 'Workspace' },
  { path: '/knowledge', label: 'Knowledge' },
  { path: '/skills', label: 'Skills' },
  { path: '/metrics', label: 'Metrics' },
]

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation()

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <nav style={{
        width: 220,
        background: 'var(--bg-card)',
        borderRight: '1px solid var(--border)',
        padding: '20px 0',
        flexShrink: 0,
      }}>
        <div style={{ padding: '0 20px 24px', borderBottom: '1px solid var(--border)' }}>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--accent)' }}>
            DevBuddy Lite
          </h1>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            Autonomous Engineer
          </p>
        </div>
        <ul style={{ listStyle: 'none', marginTop: 12 }}>
          {NAV_ITEMS.map(item => (
            <li key={item.path}>
              <Link
                to={item.path}
                style={{
                  display: 'block',
                  padding: '10px 20px',
                  fontSize: 14,
                  color: location.pathname === item.path ? 'var(--accent)' : 'var(--text-muted)',
                  background: location.pathname === item.path ? 'var(--bg-hover)' : 'transparent',
                  borderLeft: location.pathname === item.path ? '3px solid var(--accent)' : '3px solid transparent',
                  transition: 'all 0.15s',
                }}
              >
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      {/* Main content */}
      <main style={{ flex: 1, padding: 32, overflow: 'auto' }}>
        {children}
      </main>
    </div>
  )
}
