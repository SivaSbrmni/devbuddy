import { useEffect, useState } from 'react'
import Icon from './Icon'

interface ToastItem {
  id: string
  message: string
  type: 'success' | 'error' | 'info'
}

let toastListeners: ((toast: ToastItem) => void)[] = []

export function toast(message: string, type: ToastItem['type'] = 'info') {
  const t = { id: crypto.randomUUID(), message, type }
  toastListeners.forEach(l => l(t))
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  useEffect(() => {
    const handler = (t: ToastItem) => {
      setToasts(prev => [...prev, t])
      const duration = t.type === 'error' ? 6000 : t.type === 'success' ? 4000 : 3000
      setTimeout(() => {
        setToasts(prev => prev.filter(x => x.id !== t.id))
      }, duration)
    }
    toastListeners.push(handler)
    return () => {
      toastListeners = toastListeners.filter(l => l !== handler)
    }
  }, [])

  const dismiss = (id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }

  if (toasts.length === 0) return null

  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      style={{
        position: 'fixed',
        top: 20,
        right: 20,
        zIndex: 200,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      {toasts.map(t => (
        <div
          key={t.id}
          role="alert"
          style={{
            background: t.type === 'error' ? 'rgba(239,68,68,0.9)' : t.type === 'success' ? 'rgba(16,185,129,0.9)' : 'rgba(99,102,241,0.9)',
            backdropFilter: 'blur(8px)',
            color: 'white',
            padding: '10px 14px',
            borderRadius: 10,
            fontSize: 13,
            fontWeight: 500,
            boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
            animation: 'toastIn 0.3s ease',
            maxWidth: 340,
            display: 'flex',
            alignItems: 'flex-start',
            gap: 10,
          }}
        >
          <span style={{ flex: 1, lineHeight: 1.4 }}>{t.message}</span>
          <button
            onClick={() => dismiss(t.id)}
            aria-label="Dismiss notification"
            style={{
              background: 'none',
              border: 'none',
              color: 'rgba(255,255,255,0.7)',
              cursor: 'pointer',
              padding: 2,
              fontSize: 12,
              flexShrink: 0,
              marginTop: 1,
            }}
          >
            <Icon name="close" size={12} />
          </button>
        </div>
      ))}
      <style>{`
        @keyframes toastIn {
          from { opacity: 0; transform: translateX(30px); }
          to { opacity: 1; transform: translateX(0); }
        }
      `}</style>
    </div>
  )
}
