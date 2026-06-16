import { Component, ReactNode } from 'react'
import Icon from './Icon'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info)
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback
      return (
        <div style={{
          minHeight: '100vh',
          background: 'var(--bg)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 24,
          gap: 20,
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        }}>
          <Icon name="error" size={48} style={{ color: 'var(--error)', opacity: 0.6 }} />
          <h1 style={{ margin: 0, fontSize: 20, color: 'var(--text)', fontWeight: 700 }}>
            Something went wrong
          </h1>
          <p style={{ margin: 0, fontSize: 14, color: 'var(--text-muted)', textAlign: 'center', maxWidth: 400, lineHeight: 1.6 }}>
            DevBuddy encountered an unexpected error. Your conversations are safe on the server.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="db-btn db-focus"
            style={{
              padding: '10px 20px',
              background: 'var(--accent)',
              color: 'white',
              border: 'none',
              borderRadius: 'var(--radius-md)',
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <Icon name="refresh" size={14} /> Reload DevBuddy
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
