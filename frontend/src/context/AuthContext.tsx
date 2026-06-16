import { createContext, useContext, useEffect, useState, ReactNode, useRef, useCallback } from 'react'

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

const AUTH_STORAGE_KEY = 'devbuddy_token'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const abortRef = useRef<AbortController | null>(null)

  // Validate token on mount
  const validateToken = useCallback(async (token: string, signal: AbortSignal) => {
    try {
      const r = await fetch(`${BACKEND}/api/v1/auth/me?token=${encodeURIComponent(token)}`, { signal })
      if (r.status === 401) {
        // Token expired or invalid — clear it
        localStorage.removeItem(AUTH_STORAGE_KEY)
        return null
      }
      if (!r.ok) return null
      return await r.json()
    } catch {
      return null
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    abortRef.current = controller

    // Handle ?token= from OAuth redirect
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')
    if (token) {
      localStorage.setItem(AUTH_STORAGE_KEY, token)
      window.history.replaceState({}, '', window.location.pathname)
    }

    const stored = localStorage.getItem(AUTH_STORAGE_KEY)
    if (!stored) {
      setLoading(false)
      return
    }

    validateToken(stored, controller.signal).then(u => {
      if (!controller.signal.aborted) {
        setUser(u)
        setLoading(false)
      }
    })

    return () => {
      controller.abort()
    }
  }, [validateToken])

  // Cross-tab auth sync: listen for token changes in other tabs
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === AUTH_STORAGE_KEY) {
        if (e.newValue) {
          // Another tab logged in — validate the new token
          validateToken(e.newValue, new AbortController().signal).then(u => {
            setUser(u)
          })
        } else {
          // Another tab logged out
          setUser(null)
        }
      }
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [validateToken])

  // Periodic token validation (every 5 minutes)
  useEffect(() => {
    if (!user) return
    const interval = setInterval(() => {
      const stored = localStorage.getItem(AUTH_STORAGE_KEY)
      if (!stored) {
        setUser(null)
        return
      }
      validateToken(stored, new AbortController().signal).then(u => {
        if (!u) {
          setUser(null)
        }
      })
    }, 300000) // 5 minutes
    return () => clearInterval(interval)
  }, [user, validateToken])

  const login = () => {
    window.location.href = `${BACKEND}/api/v1/auth/google/login`
  }

  const logout = () => {
    localStorage.removeItem(AUTH_STORAGE_KEY)
    setUser(null)
    // Broadcast logout to other tabs
    window.dispatchEvent(new StorageEvent('storage', {
      key: AUTH_STORAGE_KEY,
      oldValue: 'x',
      newValue: null,
    }))
    window.location.href = '/'
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
