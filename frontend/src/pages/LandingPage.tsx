import { useState } from 'react'

export default function LandingPage() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)

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
      background: 'linear-gradient(135deg, #0f1117 0%, #1a1d27 50%, #0f1117 100%)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Background glow */}
      <div style={{
        position: 'absolute', top: '20%', left: '50%', transform: 'translateX(-50%)',
        width: '600px', height: '600px',
        background: 'radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      {/* Badge */}
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: '8px',
        background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.3)',
        borderRadius: '999px', padding: '6px 16px', marginBottom: '32px',
        fontSize: '13px', color: '#818cf8', fontWeight: 600,
        backdropFilter: 'blur(8px)',
      }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#6366f1', display: 'inline-block', boxShadow: '0 0 8px #6366f1' }} />
        Invite Only — Private Beta
      </div>

      {/* Logo + Title */}
      <div style={{ textAlign: 'center', marginBottom: '20px' }}>
        <div style={{
          fontSize: '52px', fontWeight: 800, letterSpacing: '-2px',
          background: 'linear-gradient(135deg, #e4e6eb 0%, #818cf8 100%)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          marginBottom: '4px',
        }}>
          DevBuddy
        </div>
        <p style={{ fontSize: '20px', color: '#8b8fa3', fontWeight: 400, maxWidth: '480px', lineHeight: 1.5 }}>
          Your AI-powered engineering co-pilot. Ship faster, debug smarter, stay in flow.
        </p>
      </div>

      {/* Feature pills */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', justifyContent: 'center', marginBottom: '48px' }}>
        {['⚡ AI Code Review', '🔍 Smart Debugging', '📊 Dev Metrics', '🧠 Knowledge Base', '🚀 Project Insights'].map(f => (
          <span key={f} style={{
            background: 'rgba(26,29,39,0.8)', border: '1px solid #2a2d3a',
            borderRadius: '8px', padding: '6px 14px', fontSize: '13px', color: '#c4c6d4',
          }}>{f}</span>
        ))}
      </div>

      {/* Card */}
      <div style={{
        background: 'rgba(26,29,39,0.85)', border: '1px solid #2a2d3a',
        borderRadius: '16px', padding: '36px 40px', maxWidth: '440px', width: '100%',
        backdropFilter: 'blur(12px)',
        boxShadow: '0 8px 40px rgba(0,0,0,0.4)',
      }}>
        {submitted ? (
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '40px', marginBottom: '16px' }}>🎉</div>
            <div style={{ fontSize: '18px', fontWeight: 700, color: '#e4e6eb', marginBottom: '8px' }}>You're on the list!</div>
            <p style={{ color: '#8b8fa3', fontSize: '14px' }}>We'll reach out to <strong style={{ color: '#818cf8' }}>{email}</strong> when your invite is ready.</p>
          </div>
        ) : (
          <>
            <div style={{ marginBottom: '20px' }}>
              <div style={{ fontSize: '17px', fontWeight: 700, color: '#e4e6eb', marginBottom: '6px' }}>Request early access</div>
              <p style={{ color: '#8b8fa3', fontSize: '14px' }}>DevBuddy is currently invite-only. Drop your email and we'll let you in when a spot opens.</p>
            </div>
            <form onSubmit={handleSubmit}>
              <input
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                style={{
                  width: '100%', padding: '11px 14px', borderRadius: '8px',
                  border: '1px solid #2a2d3a', background: '#0f1117',
                  color: '#e4e6eb', fontSize: '14px', marginBottom: '12px',
                  outline: 'none',
                }}
              />
              <button type="submit" disabled={loading} style={{
                width: '100%', padding: '11px', borderRadius: '8px',
                background: loading ? '#4b4f63' : 'linear-gradient(135deg, #6366f1, #818cf8)',
                color: 'white', fontWeight: 700, fontSize: '15px',
                border: 'none', cursor: loading ? 'not-allowed' : 'pointer', letterSpacing: '0.3px',
              }}>
                {loading ? 'Sending…' : 'Request Invite →'}
              </button>
            </form>
          </>
        )}
      </div>

      {/* Footer */}
      <p style={{ marginTop: '36px', color: '#4b4f63', fontSize: '13px' }}>
        © 2026 DevBuddy · Invite-only private beta
      </p>
    </div>
  )
}
