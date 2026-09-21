import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth'

export default function LoginPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  // FIX: use VITE_API_URL env var — same pattern as everywhere else
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'

  useEffect(() => {
    if (user) navigate('/dashboard', { replace: true })
  }, [user])

  return (
    <div style={{
      minHeight: '100vh', background: '#0f172a',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'system-ui, sans-serif',
    }}>
      {/* Background glow */}
      <div style={{
        position: 'fixed', top: '20%', left: '50%', transform: 'translateX(-50%)',
        width: 600, height: 300,
        background: 'radial-gradient(ellipse, rgba(99,102,241,0.08) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      <div style={{ width: '100%', maxWidth: 400, padding: 24 }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <div style={{
            width: 56, height: 56, borderRadius: 14,
            background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 24, fontWeight: 800, color: '#fff', margin: '0 auto 16px',
          }}>N</div>
          <h1 style={{
            color: '#e2e8f0', fontSize: 28, fontWeight: 700, margin: 0, letterSpacing: '-1px',
          }}>
            NEXUS
          </h1>
          <p style={{ color: '#475569', fontSize: 14, marginTop: 6 }}>
            Agentic Codebase Modernization
          </p>
        </div>

        {/* Card */}
        <div style={{
          background: '#0a0f1e', border: '1px solid #1e293b', borderRadius: 16, padding: 32,
        }}>
          <h2 style={{
            color: '#94a3b8', fontSize: 14, fontWeight: 600,
            margin: '0 0 24px', textAlign: 'center', letterSpacing: '0.05em',
          }}>
            SIGN IN TO CONTINUE
          </h2>

          {/* Google — FIX: href points to backend /auth/google/login */}
          <a
            href={`${apiUrl}/auth/google/login`}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
              padding: '12px 20px', borderRadius: 10,
              background: '#fff', color: '#1e293b',
              textDecoration: 'none', fontSize: 14, fontWeight: 600,
              marginBottom: 12, transition: 'opacity 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.opacity = '0.9'}
            onMouseLeave={e => e.currentTarget.style.opacity = '1'}
          >
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Continue with Google
          </a>

          {/* GitHub — FIX: href points to backend /auth/github/login */}
          <a
            href={`${apiUrl}/auth/github/login`}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
              padding: '12px 20px', borderRadius: 10,
              background: '#161b22', border: '1px solid #30363d', color: '#e2e8f0',
              textDecoration: 'none', fontSize: 14, fontWeight: 600,
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.background = '#21262d'}
            onMouseLeave={e => e.currentTarget.style.background = '#161b22'}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/>
            </svg>
            Continue with GitHub
          </a>

          <p style={{
            color: '#334155', fontSize: 11, textAlign: 'center', marginTop: 20, lineHeight: 1.5,
          }}>
            Google sign-in is recommended — your profile photo and email are used for reports.
            GitHub sign-in loads your repos directly.
          </p>
        </div>

        {/* Feature highlights */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: 24, marginTop: 28 }}>
          {['AST-first analysis', '11-layer pipeline', 'Human approval gate'].map(f => (
            <div key={f} style={{ color: '#334155', fontSize: 11, textAlign: 'center' }}>
              <div style={{ color: '#475569', marginBottom: 2 }}>✦</div>
              {f}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}