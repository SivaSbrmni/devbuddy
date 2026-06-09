import { useAuth } from '../context/AuthContext'

export default function LoginGate({ children }: { children: React.ReactNode }) {
  const { user, loading, login } = useAuth()

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: '#0d0f14', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ color: '#4b4f63', fontSize: 14 }}>Loading...</div>
      </div>
    )
  }

  if (!user) {
    return (
      <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #0f1117 0%, #1a1d27 50%, #0f1117 100%)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' }}>
        <div style={{ position: 'absolute', top: '20%', left: '50%', transform: 'translateX(-50%)', width: 500, height: 500, background: 'radial-gradient(circle, rgba(99,102,241,0.1) 0%, transparent 70%)', pointerEvents: 'none' }} />

        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <div style={{ fontSize: 48, fontWeight: 800, letterSpacing: '-2px', background: 'linear-gradient(135deg, #e4e6eb, #818cf8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', marginBottom: 8 }}>DevBuddy</div>
          <p style={{ color: '#6b7280', fontSize: 16 }}>AI Engineering Co-pilot · Invite only</p>
        </div>

        <div style={{ background: 'rgba(26,29,39,0.85)', border: '1px solid #2a2d3a', borderRadius: 16, padding: '36px 40px', maxWidth: 380, width: '100%', backdropFilter: 'blur(12px)', boxShadow: '0 8px 40px rgba(0,0,0,0.4)', textAlign: 'center' }}>
          <div style={{ fontSize: 17, fontWeight: 700, color: '#e4e6eb', marginBottom: 8 }}>Sign in to continue</div>
          <p style={{ color: '#6b7280', fontSize: 14, marginBottom: 28 }}>Access is restricted to invited users only.</p>
          <button onClick={login} style={{ width: '100%', padding: '12px', borderRadius: 10, background: 'white', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, fontSize: 15, fontWeight: 600, color: '#1a1d27' }}>
            <svg width="18" height="18" viewBox="0 0 48 48">
              <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
              <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
              <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
              <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.31-8.16 2.31-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
            </svg>
            Continue with Google
          </button>
        </div>

        <p style={{ marginTop: 24, color: '#374151', fontSize: 12 }}>© 2026 DevBuddy · Invite-only private beta</p>
      </div>
    )
  }

  return <>{children}</>
}
