import { useAuth } from '../context/AuthContext'

export default function LoginGate({ children }: { children: React.ReactNode }) {
  const { user, loading, login } = useAuth()

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
        <div style={{
          width: 40, height: 40,
          border: '3px solid var(--accent-glow)',
          borderTopColor: 'var(--accent)',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite'
        }} />
        <div style={{ color: 'var(--text-dim)', fontSize: 14, fontWeight: 500, letterSpacing: '0.3px' }}>Loading DevBuddy...</div>
      </div>
    )
  }

  if (!user) {
    return (
      <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, var(--bg) 0%, var(--bg-elevated) 50%, var(--bg) 100%)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', padding: 20, position: 'relative', overflow: 'hidden' }}>
        {/* Ambient glows */}
        <div style={{ position: 'fixed', top: '10%', left: '50%', transform: 'translateX(-50%)', width: 600, height: 600, background: 'radial-gradient(circle, rgba(99,102,241,0.08) 0%, transparent 60%)', pointerEvents: 'none' }} />
        <div style={{ position: 'fixed', bottom: '5%', right: '15%', width: 300, height: 300, background: 'radial-gradient(circle, rgba(52,211,153,0.05) 0%, transparent 60%)', pointerEvents: 'none' }} />

        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 40, position: 'relative', zIndex: 1, animation: 'fadeInScale 0.5s ease' }}>
          <div style={{
            fontSize: 48, fontWeight: 800, letterSpacing: '-2px',
            background: 'linear-gradient(135deg, var(--text), var(--accent-hover))',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            marginBottom: 12
          }}>DevBuddy</div>
          <p style={{ color: 'var(--text-dim)', fontSize: 16, lineHeight: 1.6, maxWidth: 400 }}>
            Your autonomous engineering partner. Describe what you want to build, and DevBuddy designs, codes, tests, and deploys it.
          </p>
        </div>

        {/* Features */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 36, flexWrap: 'wrap', justifyContent: 'center', position: 'relative', zIndex: 1, animation: 'fadeIn 0.6s ease' }}>
          {[
            { icon: '⚡', label: 'Autonomous Agents' },
            { icon: '🧠', label: 'Multi-LLM Routing' },
            { icon: '🔧', label: 'MCP Tools' },
            { icon: '🚀', label: 'One-Click Deploy' },
          ].map(f => (
            <div key={f.label} style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              padding: '8px 14px',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 13,
              color: 'var(--text-muted)'
            }}>
              <span>{f.icon}</span>
              {f.label}
            </div>
          ))}
        </div>

        {/* Login card */}
        <div style={{
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-xl)',
          padding: '36px 40px',
          maxWidth: 400,
          width: '100%',
          backdropFilter: 'blur(16px)',
          boxShadow: 'var(--shadow-xl), inset 0 1px 0 rgba(255,255,255,0.04)',
          textAlign: 'center',
          position: 'relative',
          zIndex: 1,
          animation: 'fadeInScale 0.7s ease',
        }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)', marginBottom: 6 }}>Welcome back</div>
          <p style={{ color: 'var(--text-dim)', fontSize: 14, marginBottom: 28, lineHeight: 1.5 }}>
            Sign in with Google to access your workspace
          </p>
          <button
            onClick={login}
            className="db-btn"
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: 'var(--radius-lg)',
              background: 'white',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 10,
              fontSize: 15,
              fontWeight: 600,
              color: 'var(--bg)',
              transition: 'all var(--transition-base)',
            }}
            onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-1px)'; e.currentTarget.style.boxShadow = 'var(--shadow-md)' }}
            onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none' }}
          >
            <svg width="18" height="18" viewBox="0 0 48 48">
              <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
              <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
              <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
              <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.31-8.16 2.31-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
            </svg>
            Continue with Google
          </button>
        </div>

        <p style={{ marginTop: 32, color: 'var(--text-faint)', fontSize: 12, position: 'relative', zIndex: 1 }}>
          © 2026 DevBuddy · Autonomous Engineering Platform
        </p>
      </div>
    )
  }

  return <>{children}</>
}
