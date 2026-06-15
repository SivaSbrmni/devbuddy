import { useAuth } from '../context/AuthContext'
import Icon from './Icon'

export default function LoginOverlay() {
  const { login } = useAuth()

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(13,15,20,0.85)',
      backdropFilter: 'blur(12px)',
      zIndex: 1000,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      animation: 'fadeIn 0.3s ease',
    }}>
      <div style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-xl)',
        padding: '48px 40px',
        maxWidth: 420,
        width: '90%',
        textAlign: 'center',
        boxShadow: 'var(--shadow-lg), 0 0 80px rgba(99,102,241,0.1)',
        animation: 'modalContent 0.3s ease',
      }}>
        <div style={{
          width: 56,
          height: 56,
          borderRadius: 'var(--radius-lg)',
          background: 'linear-gradient(135deg, var(--accent), var(--accent-hover))',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 24px',
          boxShadow: '0 8px 24px rgba(99,102,241,0.3)',
        }}>
          <Icon name="sparkles" size={28} style={{ color: 'white' }} />
        </div>

        <h1 style={{
          fontSize: 24,
          fontWeight: 800,
          color: 'var(--text)',
          margin: '0 0 8px',
          letterSpacing: '-0.5px',
        }}>DevBuddy</h1>

        <p style={{
          fontSize: 15,
          color: 'var(--text-muted)',
          margin: '0 0 32px',
          lineHeight: 1.6,
        }}>
          Your AI engineering co-pilot. Ship faster, debug smarter, stay in flow.
        </p>

        <button
          onClick={login}
          className="db-btn db-focus"
          style={{
            width: '100%',
            padding: '12px 20px',
            background: 'var(--text)',
            border: 'none',
            borderRadius: 'var(--radius-md)',
            color: 'var(--bg)',
            fontSize: 14,
            fontWeight: 700,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 10,
            transition: 'all var(--transition-base)',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.transform = 'translateY(-1px)'
            e.currentTarget.style.boxShadow = '0 4px 16px rgba(255,255,255,0.15)'
          }}
          onMouseLeave={e => {
            e.currentTarget.style.transform = 'translateY(0)'
            e.currentTarget.style.boxShadow = 'none'
          }}
        >
          <svg width="18" height="18" viewBox="0 0 18 18"><path fill="#4285F4" d="M17.64 9.2c0-.63-.06-1.25-.16-1.84H9v3.49h4.84a4.14 4.14 0 01-1.8 2.71v2.26h2.92a8.78 8.78 0 002.68-6.62z"/><path fill="#34A853" d="M9 18a8.58 8.58 0 005.96-2.18l-2.92-2.26a5.42 5.42 0 01-8.08-2.85H1.32v2.33A9 9 0 009 18z"/><path fill="#FBBC05" d="M3.96 10.71a5.36 5.36 0 010-3.42V4.96H1.32a9.02 9.02 0 000 8.08l2.64-2.33z"/><path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.34l2.58-2.58A8.58 8.58 0 001.32 4.96l2.64 2.33a5.42 5.42 0 015.04-3.71z"/></svg>
          Continue with Google
        </button>

        <p style={{
          fontSize: 12,
          color: 'var(--text-faint)',
          marginTop: 20,
          lineHeight: 1.5,
        }}>
          By continuing, you agree to our Terms of Service and Privacy Policy.
        </p>
      </div>
    </div>
  )
}
