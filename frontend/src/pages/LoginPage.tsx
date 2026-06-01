import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/button'
import { Bot, Shield, Zap, Globe } from 'lucide-react'

export function LoginPage() {
  const { user, loading, signInWithGoogle, devSignIn } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!loading && user) navigate('/dashboard')
  }, [user, loading, navigate])

  return (
    <div className="min-h-screen bg-background flex">
      {/* Left panel */}
      <div className="hidden lg:flex lg:flex-1 flex-col justify-between p-12 bg-gradient-to-br from-primary/10 via-background to-background border-r border-border">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/20 flex items-center justify-center">
            <Bot className="w-6 h-6 text-primary" />
          </div>
          <div>
            <p className="font-bold text-foreground">DevBuddy</p>
            <p className="text-xs text-muted-foreground">Enterprise Agent Platform</p>
          </div>
        </div>

        <div className="space-y-8">
          <div>
            <h1 className="text-4xl font-bold text-foreground leading-tight">
              Autonomous coding<br />
              <span className="text-primary">at enterprise scale</span>
            </h1>
            <p className="mt-4 text-muted-foreground text-lg max-w-md">
              Deterministic orchestration. Policy-driven autonomy. Immutable audit trails.
              Built for regulated enterprises.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 max-w-sm">
            {[
              { icon: Shield, label: 'Policy Enforcement', desc: 'Every action evaluated and audited' },
              { icon: Zap, label: 'Real-time Execution', desc: 'Live streaming agent execution logs' },
              { icon: Globe, label: 'Multi-tenant', desc: 'Isolated per organization with tenant-scoped data' },
            ].map(({ icon: Icon, label, desc }) => (
              <div key={label} className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                  <Icon className="w-4 h-4 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">{label}</p>
                  <p className="text-xs text-muted-foreground">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          © 2026 DevBuddy.org — Enterprise Autonomous Agent Platform
        </p>
      </div>

      {/* Right panel */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm space-y-8">
          <div className="text-center lg:text-left">
            <div className="flex items-center gap-2 justify-center lg:justify-start mb-6 lg:hidden">
              <Bot className="w-8 h-8 text-primary" />
              <span className="font-bold text-xl">DevBuddy</span>
            </div>
            <h2 className="text-2xl font-bold text-foreground">Welcome back</h2>
            <p className="mt-2 text-muted-foreground text-sm">
              Sign in with your Google account to access the platform.
            </p>
          </div>

          <div className="space-y-3">
            <Button
              onClick={signInWithGoogle}
              disabled={loading}
              className="w-full h-12 text-base font-medium gap-3"
              variant="outline"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              Continue with Google
            </Button>

            <div className="relative flex items-center gap-2">
              <div className="flex-1 h-px bg-border" />
              <span className="text-xs text-muted-foreground">or</span>
              <div className="flex-1 h-px bg-border" />
            </div>
            <Button
              onClick={() => devSignIn()}
              disabled={loading}
              className="w-full h-10 text-sm font-medium gap-2"
              variant="secondary"
            >
              Dev Sign In
            </Button>
          </div>

          <p className="text-center text-xs text-muted-foreground">
            By signing in you agree to our terms of service and privacy policy.
            <br />Enterprise SSO available for dedicated deployments.
          </p>
        </div>
      </div>
    </div>
  )
}
