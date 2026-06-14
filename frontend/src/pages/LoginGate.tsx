import { useAuth } from '../context/AuthContext'

export default function LoginGate({ children }: { children: React.ReactNode }) {
  const { user, loading, login } = useAuth()

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: '#0d0f14', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
        <div style={{
          width: 40, height: 40,
          border: '3px solid rgba(99,102,241,0.2)',
          borderTopColor: '#6366f1',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite'
        }} />
        <div style={{ color: '#6b7280', fontSize: 14, fontWeight: 500 }}>Loading DevBuddy...</div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }

  if (!user) {
    return (
      <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #0a0c10 0%, #111318 50%, #0a0c10 100%)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', padding: 20 }}>
        {/* Ambient glow */}
        <div style={{ position: 'fixed', top: '10%', left: '50%', transform: 'translateX(-50%)', width: 600, height: 600, background: 'radial-gradient(circle, rgba(99,102,241,0.08) 0%, transparent 60%)', pointerEvents: 'none' }} />

        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 48, position: 'relative', zIndex: 1 }}>
          <div style={{
            fontSize: 52, fontWeight: 800, letterSpacing: '-2px',
            background: 'linear-gradient(135deg, #e4e6eb, #818cf8)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            marginBottom: 12
          }}>DevBuddy</div>
          <p style={{ color: '#6b7280', fontSize: 17, lineHeight: 1.5, maxWidth: 400 }}>
            Your autonomous engineering partner. Describe what you want to build, and DevBuddy designs, codes, tests, and deploys it.
          </p>
        </div>

        {/* Features */}
        <div style={{ display: 'flex', gap: 16, marginBottom: 40, flexWrap: 'wrap', justifyContent: 'center', position: 'relative', zIndex: 1 }}>
          {[
            { icon: '⚡', label: 'Autonomous Agents' },
            { icon: '🧠', label: 'Multi-LLM Routing' },
            { icon: '🔧', label: 'MCP Tools' },
            { icon: '🚀', label: 'One-Click Deploy' },
          ].map(f => (
            <div key={f.label} style={{
              background: 'rgba(26,29,39,0.6)',
              border: '1px solid #2a2d3a',
              borderRadius: 10,
              padding: '10px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 13,
              color: '#9ca3af'
            }}>
              <span>{f.icon}</span>
              {f.label}
            </div>
          ))}
        </div>

        {/* Login card */}
        <div style={{
          background: 'rgba(17,19,24,0.95)',
          border: '1px solid #2a2d3a',
          borderRadius: 20,
          padding: '40px 44px',
          maxWidth: 400,
          width: '100%',
          backdropFilter: 'blur(16px)',
          boxShadow: '0 16px 60px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04)',
          textAlign: 'center',
          position: 'relative',
          zIndex: 1
        }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#e4e6eb', marginBottom: 6 }}>Welcome back</div>
          <p style={{ color: '#6b7280', fontSize: 14, marginBottom: 28, lineHeight: 1.5 }}>
            Sign in with Google to access your workspace
          </p>
          <button
            onClick={login}
            onMouseEnter={e => { (e.target as HTMLButtonElement).style.transform = 'translateY(-1px)'; (e.target as HTMLButtonElement).style.boxShadow = '0 4px 12px rgba(0,0,0,0.2)' }}
            onMouseLeave={e => { (e.target as HTMLButtonElement).style.transform = 'translateY(0)'; (e.target as HTMLButtonElement).style.boxShadow = 'none' }}
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: 12,
              background: 'white',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 10,
              fontSize: 15,
              fontWeight: 600,
              color: '#1a1d27',
              transition: 'all 0.2s ease'
            }}
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

        <p style={{ marginTop: 32, color: '#374151', fontSize: 12, position: 'relative', zIndex: 1 }}>
          © 2026 DevBuddy · Autonomous Engineering Platform
        </p>
      </div>
    )
  }

  return <>{children}</>
}
