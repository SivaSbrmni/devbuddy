import { useEffect, useState } from 'react'

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
      setTimeout(() => {
        setToasts(prev => prev.filter(x => x.id !== t.id))
      }, 3000)
    }
    toastListeners.push(handler)
    return () => {
      toastListeners = toastListeners.filter(l => l !== handler)
    }
  }, [])

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
            padding: '10px 16px',
            borderRadius: 10,
            fontSize: 13,
            fontWeight: 500,
            boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
            animation: 'toastIn 0.3s ease, toastOut 0.3s ease 2.7s',
            maxWidth: 320,
          }}
        >
          {t.message}
        </div>
      ))}
      <style>{`
        @keyframes toastIn {
          from { opacity: 0; transform: translateX(30px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes toastOut {
          from { opacity: 1; transform: translateX(0); }
          to { opacity: 0; transform: translateX(30px); }
        }
      `}</style>
    </div>
  )
}
