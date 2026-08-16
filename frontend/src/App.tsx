import { lazy, Suspense, useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import ErrorBoundary from './components/ErrorBoundary'
import LandingPage from './pages/LandingPage'

const Workspace = lazy(() => import('./pages/Workspace'))
const SessionWorkspace = lazy(() => import('./pages/SessionWorkspace'))
const LoginGate = lazy(() => import('./pages/LoginGate'))

function AuthSkeleton() {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20, padding: 24 }}>
      <div className="db-skeleton" style={{ width: 48, height: 48, borderRadius: 14 }} />
      <div className="db-skeleton" style={{ width: 200, height: 20, borderRadius: 6 }} />
      <div className="db-skeleton" style={{ width: 280, height: 48, borderRadius: 12 }} />
    </div>
  )
}

function AppRoutes() {
  const { user, loading } = useAuth()
  const [isOnline, setIsOnline] = useState(navigator.onLine)

  useEffect(() => {
    const on = () => { setIsOnline(true) }
    const off = () => { setIsOnline(false) }
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
    }
  }, [])

  if (loading) {
    return <AuthSkeleton />
  }

  return (
    <>
      {!isOnline && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 9999,
          background: 'var(--warning)',
          color: '#000',
          fontSize: 13,
          fontWeight: 600,
          padding: '8px 16px',
          textAlign: 'center',
        }}>
          You are offline. Some features may not work until your connection is restored.
        </div>
      )}
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route
          path="/app/session/:sessionId"
          element={
            <Suspense fallback={<AuthSkeleton />}>
              {user ? <SessionWorkspace /> : <LoginGate />}
            </Suspense>
          }
        />
        <Route
          path="/app"
          element={
            <Suspense fallback={<AuthSkeleton />}>
              {user ? <Workspace /> : <LoginGate />}
            </Suspense>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ErrorBoundary>
          <AppRoutes />
        </ErrorBoundary>
      </AuthProvider>
    </BrowserRouter>
  )
}
