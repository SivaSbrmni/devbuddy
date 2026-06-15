import { AuthProvider, useAuth } from './context/AuthContext'
import Workspace from './pages/Workspace'
import LoginOverlay from './components/LoginOverlay'

function AppContent() {
  const { user, loading } = useAuth()
  if (loading) return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ width: 32, height: 32, border: '2px solid var(--border)', borderTopColor: 'var(--accent)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
    </div>
  )
  return (
    <>
      <Workspace />
      {!user && <LoginOverlay />}
    </>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}
