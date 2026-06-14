import { Routes, Route, Navigate } from 'react-router-dom'
import LandingPage from './pages/LandingPage'
import ChatPage from './pages/ChatPage'
import LoginGate from './pages/LoginGate'
import { AuthProvider } from './context/AuthContext'

const isDevDomain = window.location.hostname === 'dev.devbuddy.org' || window.location.hostname === 'sivasbrmni-devbuddy.hf.space'

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        {isDevDomain ? (
          <>
            <Route path="/" element={<LoginGate><ChatPage /></LoginGate>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </>
        ) : (
          <>
            <Route path="/" element={<LandingPage />} />
            <Route path="/app" element={<LoginGate><ChatPage /></LoginGate>} />
            <Route path="/app/*" element={<LoginGate><ChatPage /></LoginGate>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </>
        )}
      </Routes>
    </AuthProvider>
  )
}
