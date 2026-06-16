import { createContext, useContext, useEffect, useState, ReactNode } from 'react'

const BACKEND = import.meta.env.VITE_API_URL || ''

interface User {
  id?: string
  email: string
  name: string
  picture: string
}

interface AuthCtx {
  user: User | null
  loading: boolean
  login: () => void
  logout: () => void
}

const AuthContext = createContext<AuthCtx>({
  user: null,
  loading: true,
  login: () => {},
  logout: () => {},
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')
    if (token) {
      localStorage.setItem('devbuddy_token', token)
      window.history.replaceState({}, '', window.location.pathname)
    }
    const stored = localStorage.getItem('devbuddy_token')
    if (!stored) { setLoading(false); return }
    fetch(`${BACKEND}/api/v1/auth/me?token=${stored}`)
      .then(r => r.ok ? r.json() : null)
      .then(u => { setUser(u); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const login = () => {
    window.location.href = `${BACKEND}/api/v1/auth/google/login`
  }

  const logout = () => {
    localStorage.removeItem('devbuddy_token')
    setUser(null)
    window.location.href = '/'
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
