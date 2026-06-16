import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import LandingPage from './pages/LandingPage'

const Workspace = lazy(() => import('./pages/Workspace'))
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

  if (loading) {
    return <AuthSkeleton />
  }

  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
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
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}
