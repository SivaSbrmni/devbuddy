import { useState } from 'react'
import Icon from '../components/Icon'

export default function LandingPage() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)
  const [hoveredPill, setHoveredPill] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email) return
    setLoading(true)
    try {
      await fetch('https://formspree.io/f/meewkbqo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ email }),
      })
      setSubmitted(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, var(--bg) 0%, var(--bg-card) 50%, var(--bg) 100%)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 'var(--space-6)',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Skip link for keyboard users */}
      <a href="#main-content" style={{
        position: 'absolute',
        top: '-40px',
        left: '50%',
        transform: 'translateX(-50%)',
        background: 'var(--accent)',
        color: 'white',
        padding: '8px 16px',
        borderRadius: 'var(--radius-md)',
        fontSize: '14px',
        fontWeight: 600,
        textDecoration: 'none',
        zIndex: 100,
        transition: 'top 0.2s ease',
      }}
      onFocus={e => { e.currentTarget.style.top = '12px' }}
      onBlur={e => { e.currentTarget.style.top = '-40px' }}
      >
        Skip to content
      </a>

      {/* Background glow */}
      <div aria-hidden="true" style={{
        position: 'absolute', top: '15%', left: '50%', transform: 'translateX(-50%)',
        width: '700px', height: '700px',
        background: 'radial-gradient(circle, rgba(99,102,241,0.1) 0%, transparent 65%)',
        pointerEvents: 'none',
      }} />
      <div aria-hidden="true" style={{
        position: 'absolute', bottom: '10%', right: '20%',
        width: '400px', height: '400px',
        background: 'radial-gradient(circle, rgba(52,211,153,0.06) 0%, transparent 60%)',
        pointerEvents: 'none',
      }} />

      {/* Badge */}
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2)',
        background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)',
        borderRadius: 'var(--radius-full)', padding: '6px 16px', marginBottom: 'var(--space-8)',
        fontSize: '13px', color: 'var(--accent-hover)', fontWeight: 600,
        backdropFilter: 'blur(8px)',
        animation: 'fadeInScale 0.5s ease',
      }}>
        <span aria-hidden="true" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)', display: 'inline-block', boxShadow: '0 0 6px var(--accent)' }} />
        Invite Only — Private Beta
      </div>

      {/* Logo + Title */}
      <header style={{ textAlign: 'center', marginBottom: 'var(--space-5)', animation: 'fadeIn 0.6s ease' }}>
        <h1 style={{
          fontSize: '56px', fontWeight: 800, letterSpacing: '-2.5px',
          background: 'linear-gradient(135deg, var(--text) 0%, var(--accent-hover) 100%)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          marginBottom: 'var(--space-2)',
          marginTop: 0,
          lineHeight: 1.1,
        }}>
          DevBuddy
        </h1>
        <p style={{ fontSize: '20px', color: 'var(--text-muted)', fontWeight: 400, maxWidth: '520px', lineHeight: 1.6, margin: 0 }}>
          Your AI-powered engineering co-pilot. Ship faster, debug smarter, stay in flow.
        </p>
      </header>

      {/* Feature pills */}
      <div role="list" aria-label="Features" style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', justifyContent: 'center', marginBottom: 'var(--space-8)', animation: 'fadeIn 0.7s ease' }}>
        {[
          { label: 'AI Code Review', icon: 'zap' },
          { label: 'Smart Debugging', icon: 'wrench' },
          { label: 'Dev Metrics', icon: 'info' },
          { label: 'Knowledge Base', icon: 'brain' },
          { label: 'Project Insights', icon: 'rocket' },
        ].map(f => (
          <span
            role="listitem"
            key={f.label}
            onMouseEnter={() => setHoveredPill(f.label)}
            onMouseLeave={() => setHoveredPill(null)}
            style={{
              background: hoveredPill === f.label ? 'rgba(99,102,241,0.1)' : 'var(--bg-card)',
              border: hoveredPill === f.label ? '1px solid rgba(99,102,241,0.3)' : '1px solid var(--border)',
              borderRadius: 'var(--radius-md)', padding: '7px 16px', fontSize: '13px', color: 'var(--text-muted)',
              cursor: 'default',
              transition: 'all var(--transition-base)',
              transform: hoveredPill === f.label ? 'translateY(-1px)' : 'translateY(0)',
            }}
          ><span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><Icon name={f.icon as any} size={14} aria-hidden="true" /> {f.label}</span></span>
        ))}
      </div>

      {/* Card */}
      <main id="main-content" style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-xl)', padding: 'var(--space-8) var(--space-8)', maxWidth: '440px', width: '100%',
        backdropFilter: 'blur(12px)',
        boxShadow: 'var(--shadow-lg)',
        animation: 'fadeInScale 0.8s ease',
      }}>
        {submitted ? (
          <div style={{ textAlign: 'center' }} role="status" aria-live="polite">
            <div style={{ fontSize: '44px', marginBottom: 'var(--space-4)' }}><Icon name="sparkles" size={40} style={{ color: 'var(--accent-hover)' }} aria-hidden="true" /></div>
            <h2 style={{ fontSize: '19px', fontWeight: 700, color: 'var(--text)', marginBottom: 'var(--space-2)', marginTop: 0 }}>You're on the list!</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '14px', lineHeight: 1.6 }}>
              We'll reach out to <strong style={{ color: 'var(--accent-hover)' }}>{email}</strong> when your invite is ready.
            </p>
          </div>
        ) : (
          <>
            <div style={{ marginBottom: 'var(--space-5)' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text)', marginBottom: '6px', marginTop: 0 }}>Request early access</h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '14px', lineHeight: 1.6, margin: 0 }}>
                DevBuddy is currently invite-only. Drop your email and we'll let you in when a spot opens.
              </p>
            </div>
            <form onSubmit={handleSubmit} noValidate>
              <label htmlFor="email-input" style={{ position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0,0,0,0)', whiteSpace: 'nowrap', border: 0 }}>
                Email address
              </label>
              <input
                id="email-input"
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                autoComplete="email"
                aria-label="Email address"
                aria-required="true"
                className="db-input"
                style={{
                  width: '100%', padding: '12px 16px', borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border)', background: 'var(--bg)',
                  color: 'var(--text)', fontSize: '15px', marginBottom: 'var(--space-3)',
                }}
              />
              <button
                type="submit"
                disabled={loading}
                className="db-btn"
                aria-label={loading ? 'Sending request' : 'Request invite'}
                style={{
                  width: '100%', padding: '12px', borderRadius: 'var(--radius-md)',
                  background: loading ? 'var(--text-faint)' : 'linear-gradient(135deg, var(--accent), var(--accent-hover))',
                  color: 'white', fontWeight: 700, fontSize: '15px',
                  border: 'none', cursor: loading ? 'not-allowed' : 'pointer', letterSpacing: '0.3px',
                }}
              >
                {loading ? 'Sending…' : 'Request Invite →'}
              </button>
            </form>
          </>
        )}
      </main>

      {/* Footer */}
      <footer style={{ marginTop: 'var(--space-8)', color: 'var(--text-faint)', fontSize: '13px', animation: 'fadeIn 1s ease' }}>
        <p style={{ margin: 0 }}>© 2026 DevBuddy · Invite-only private beta</p>
      </footer>
    </div>
  )
}
