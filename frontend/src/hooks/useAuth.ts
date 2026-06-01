import { useState, useEffect } from 'react'
import { User, Session } from '@supabase/supabase-js'
import { supabase } from '@/lib/supabase'
import { DEV_TOKEN_KEY } from '@/lib/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

interface DevUser {
  id: string
  email: string
  isDev: true
}

interface AuthState {
  user: User | DevUser | null
  session: Session | null
  loading: boolean
}

export function useAuth(): AuthState & {
  signInWithGoogle: () => Promise<void>
  devSignIn: (email?: string) => Promise<void>
  signOut: () => Promise<void>
} {
  const [state, setState] = useState<AuthState>({ user: null, session: null, loading: true })

  useEffect(() => {
    const devToken = localStorage.getItem(DEV_TOKEN_KEY)
    if (devToken) {
      try {
        const payload = JSON.parse(atob(devToken.split('.')[1]))
        setState({ user: { id: payload.sub, email: payload.email, isDev: true }, session: null, loading: false })
        return
      } catch {
        localStorage.removeItem(DEV_TOKEN_KEY)
      }
    }

    supabase.auth.getSession().then(({ data }) => {
      setState({ user: data.session?.user ?? null, session: data.session, loading: false })
    })

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setState({ user: session?.user ?? null, session, loading: false })
    })

    return () => listener.subscription.unsubscribe()
  }, [])

  const signInWithGoogle = async () => {
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin },
    })
  }

  const devSignIn = async (email = 'dev@devbuddy.local') => {
    const res = await fetch(`${API_BASE}/api/v1/auth/dev-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, name: 'Dev User' }),
    })
    if (!res.ok) throw new Error('Dev token request failed')
    const data = await res.json()
    localStorage.setItem(DEV_TOKEN_KEY, data.access_token)
    const payload = JSON.parse(atob(data.access_token.split('.')[1]))
    setState({ user: { id: payload.sub, email: payload.email, isDev: true }, session: null, loading: false })
  }

  const signOut = async () => {
    localStorage.removeItem(DEV_TOKEN_KEY)
    await supabase.auth.signOut()
    setState({ user: null, session: null, loading: false })
  }

  return { ...state, signInWithGoogle, devSignIn, signOut }
}
