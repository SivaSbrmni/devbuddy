import { useState } from 'react'

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
      {/* Background glow */}
      <div style={{
        position: 'absolute', top: '15%', left: '50%', transform: 'translateX(-50%)',
        width: '700px', height: '700px',
        background: 'radial-gradient(circle, rgba(99,102,241,0.1) 0%, transparent 65%)',
        pointerEvents: 'none',
      }} />
      <div style={{
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
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)', display: 'inline-block', boxShadow: '0 0 6px var(--accent)' }} />
        Invite Only — Private Beta
      </div>

      {/* Logo + Title */}
      <div style={{ textAlign: 'center', marginBottom: 'var(--space-5)', animation: 'fadeIn 0.6s ease' }}>
        <div style={{
          fontSize: '56px', fontWeight: 800, letterSpacing: '-2.5px',
          background: 'linear-gradient(135deg, var(--text) 0%, var(--accent-hover) 100%)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          marginBottom: 'var(--space-2)',
        }}>
          DevBuddy
        </div>
        <p style={{ fontSize: '20px', color: 'var(--text-muted)', fontWeight: 400, maxWidth: '520px', lineHeight: 1.6 }}>
          Your AI-powered engineering co-pilot. Ship faster, debug smarter, stay in flow.
        </p>
      </div>

      {/* Feature pills */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', justifyContent: 'center', marginBottom: 'var(--space-8)', animation: 'fadeIn 0.7s ease' }}>
        {['⚡ AI Code Review', '🔍 Smart Debugging', '📊 Dev Metrics', '🧠 Knowledge Base', '🚀 Project Insights'].map(f => (
          <span
            key={f}
            onMouseEnter={() => setHoveredPill(f)}
            onMouseLeave={() => setHoveredPill(null)}
            style={{
              background: hoveredPill === f ? 'rgba(99,102,241,0.1)' : 'var(--bg-card)',
              border: hoveredPill === f ? '1px solid rgba(99,102,241,0.3)' : '1px solid var(--border)',
              borderRadius: 'var(--radius-md)', padding: '7px 16px', fontSize: '13px', color: 'var(--text-muted)',
              cursor: 'default',
              transition: 'all var(--transition-base)',
              transform: hoveredPill === f ? 'translateY(-1px)' : 'translateY(0)',
            }}
          >{f}</span>
        ))}
      </div>

      {/* Card */}
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-xl)', padding: 'var(--space-8) var(--space-8)', maxWidth: '440px', width: '100%',
        backdropFilter: 'blur(12px)',
        boxShadow: 'var(--shadow-lg)',
        animation: 'fadeInScale 0.8s ease',
      }}>
        {submitted ? (
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '44px', marginBottom: 'var(--space-4)' }}>🎉</div>
            <div style={{ fontSize: '19px', fontWeight: 700, color: 'var(--text)', marginBottom: 'var(--space-2)' }}>You're on the list!</div>
            <p style={{ color: 'var(--text-muted)', fontSize: '14px', lineHeight: 1.6 }}>
              We'll reach out to <strong style={{ color: 'var(--accent-hover)' }}>{email}</strong> when your invite is ready.
            </p>
          </div>
        ) : (
          <>
            <div style={{ marginBottom: 'var(--space-5)' }}>
              <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text)', marginBottom: '6px' }}>Request early access</div>
              <p style={{ color: 'var(--text-muted)', fontSize: '14px', lineHeight: 1.6 }}>
                DevBuddy is currently invite-only. Drop your email and we'll let you in when a spot opens.
              </p>
            </div>
            <form onSubmit={handleSubmit}>
              <input
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
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
      </div>

      {/* Footer */}
      <p style={{ marginTop: 'var(--space-8)', color: 'var(--text-faint)', fontSize: '13px', animation: 'fadeIn 1s ease' }}>
        © 2026 DevBuddy · Invite-only private beta
      </p>
    </div>
  )
}
