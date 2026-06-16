import { useAuth } from '../context/AuthContext'
import Icon from '../components/Icon'
import { useState } from 'react'

export default function LoginGate({ children }: { children?: React.ReactNode }) {
  const { user, loading, login } = useAuth()
  const [hoveredFeature, setHoveredFeature] = useState<string | null>(null)

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

  if (user) {
    return <>{children}</>
  }

  const features = [
    { icon: 'zap', label: 'Autonomous Agents', desc: 'Self-directed engineering workflows' },
    { icon: 'brain', label: 'Multi-LLM Routing', desc: 'Claude, Llama, Ollama — best model for each task' },
    { icon: 'git-branch', label: 'GitHub Integration', desc: 'PR creation, code review, CI/CD' },
    { icon: 'rocket', label: 'One-Click Deploy', desc: 'Railway, Vercel, Docker — ship instantly' },
  ]

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--bg)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      padding: 'var(--space-6)',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Ambient glows */}
      <div style={{
        position: 'fixed', top: '8%', left: '50%', transform: 'translateX(-50%)',
        width: 800, height: 800,
        background: 'radial-gradient(circle, rgba(99,102,241,0.08) 0%, transparent 60%)',
        pointerEvents: 'none',
      }} />
      <div style={{
        position: 'fixed', bottom: '5%', right: '10%',
        width: 500, height: 500,
        background: 'radial-gradient(circle, rgba(52,211,153,0.05) 0%, transparent 60%)',
        pointerEvents: 'none',
      }} />

      {/* Beta badge */}
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 8,
        background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)',
        borderRadius: 'var(--radius-full)', padding: '6px 16px', marginBottom: 32,
        fontSize: 13, color: 'var(--accent-hover)', fontWeight: 600,
        animation: 'fadeInScale 0.5s ease',
      }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)', display: 'inline-block', boxShadow: '0 0 6px var(--accent)' }} />
        Invite Only — Private Beta
      </div>

      {/* Logo */}
      <div style={{ textAlign: 'center', marginBottom: 16, position: 'relative', zIndex: 1, animation: 'fadeIn 0.6s ease' }}>
        <div style={{
          fontSize: 56, fontWeight: 800, letterSpacing: '-2.5px',
          background: 'linear-gradient(135deg, var(--text) 0%, var(--accent-hover) 100%)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          marginBottom: 12,
        }}>DevBuddy</div>
        <p style={{ color: 'var(--text-muted)', fontSize: 18, lineHeight: 1.6, maxWidth: 480, margin: '0 auto' }}>
          Your autonomous engineering partner. Describe what you want to build, and DevBuddy designs, codes, tests, and deploys it.
        </p>
      </div>

      {/* Feature grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(2, 1fr)',
        gap: 12,
        maxWidth: 480,
        width: '100%',
        marginBottom: 36,
        position: 'relative', zIndex: 1,
        animation: 'fadeIn 0.7s ease',
      }}>
        {features.map(f => (
          <div
            key={f.label}
            onMouseEnter={() => setHoveredFeature(f.label)}
            onMouseLeave={() => setHoveredFeature(null)}
            style={{
              background: hoveredFeature === f.label ? 'rgba(99,102,241,0.06)' : 'var(--bg-card)',
              border: hoveredFeature === f.label ? '1px solid rgba(99,102,241,0.25)' : '1px solid var(--border)',
              borderRadius: 'var(--radius-lg)',
              padding: '16px 20px',
              transition: 'all var(--transition-base)',
              cursor: 'default',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
              <Icon name={f.icon as any} size={16} style={{ color: 'var(--accent)' }} />
              <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>{f.label}</span>
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.5, margin: 0 }}>{f.desc}</p>
          </div>
        ))}
      </div>

      {/* Login card */}
      <div style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-xl)',
        padding: '40px',
        maxWidth: 400,
        width: '100%',
        backdropFilter: 'blur(16px)',
        boxShadow: 'var(--shadow-xl), inset 0 1px 0 rgba(255,255,255,0.04)',
        textAlign: 'center',
        position: 'relative',
        zIndex: 1,
        animation: 'fadeInScale 0.8s ease',
      }}>
        <div style={{
          width: 56, height: 56, borderRadius: 'var(--radius-lg)',
          background: 'linear-gradient(135deg, var(--accent), var(--accent-hover))',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 20px',
          boxShadow: '0 8px 24px rgba(99,102,241,0.3)',
        }}>
          <Icon name="sparkles" size={28} style={{ color: 'white' }} />
        </div>

        <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)', marginBottom: 6 }}>Welcome to DevBuddy</div>
        <p style={{ color: 'var(--text-dim)', fontSize: 14, marginBottom: 28, lineHeight: 1.5 }}>
          Sign in with Google to access your workspace
        </p>

        <button
          onClick={login}
          className="db-btn db-focus"
          style={{
            width: '100%',
            padding: '12px 20px',
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

        <p style={{ marginTop: 20, color: 'var(--text-faint)', fontSize: 12, lineHeight: 1.5 }}>
          By continuing, you agree to our Terms of Service and Privacy Policy.
        </p>
      </div>

      <p style={{ marginTop: 32, color: 'var(--text-faint)', fontSize: 12, position: 'relative', zIndex: 1 }}>
        © 2026 DevBuddy · Autonomous Engineering Platform
      </p>
    </div>
  )
}
