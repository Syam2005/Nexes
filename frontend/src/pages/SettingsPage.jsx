import { useState } from 'react'
import { useAuth } from '../store/auth'
import api from '../utils/api'
import toast from 'react-hot-toast'

function Toggle({ value, onChange, disabled }) {
  return (
    <div
      onClick={() => !disabled && onChange(!value)}
      style={{
        width: 44, height: 24, borderRadius: 12,
        cursor: disabled ? 'not-allowed' : 'pointer',
        background: value && !disabled ? 'var(--brand)' : 'var(--border)',
        border: `1px solid ${value && !disabled ? 'var(--brand-muted)' : 'var(--border-muted)'}`,
        position: 'relative', transition: 'all 0.2s', flexShrink: 0,
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <div style={{
        width: 16, height: 16, borderRadius: '50%', background: '#fff',
        position: 'absolute', top: 3,
        left: value && !disabled ? 23 : 3,
        transition: 'left 0.2s',
      }} />
    </div>
  )
}

const isRealEmail = (email) =>
  email && !email.includes('@github.noemail')

export default function SettingsPage() {
  const { user, refreshUser } = useAuth()

  const hasRealEmail = isRealEmail(user?.email)

  const [emailReports, setEmailReports]   = useState(
    // Force off if no real email
    hasRealEmail ? (user?.email_reports ?? true) : false
  )
  const [riskThreshold, setRiskThreshold] = useState(user?.risk_threshold || 'MEDIUM')
  const [theme, setTheme]                 = useState(user?.theme || 'dark')
  const [saving, setSaving]               = useState(false)

  const applyTheme = (t) => {
    document.documentElement.setAttribute('data-theme', t)
    setTheme(t)
  }

  const save = async () => {
    setSaving(true)
    try {
      await api.patch('/me/settings', {
        email_reports:  hasRealEmail ? emailReports : false,
        risk_threshold: riskThreshold,
        theme,
      })
      document.documentElement.setAttribute('data-theme', theme)
      await refreshUser()
      toast.success('Settings saved')
    } catch {
      toast.error('Save failed')
    } finally {
      setSaving(false)
    }
  }

  const cardStyle = {
    background: 'var(--bg-surface)',
    border: '1px solid var(--border)',
    borderRadius: 10,
    padding: 20,
  }

  return (
    <div style={{ padding: '24px 32px', maxWidth: 560, margin: '0 auto' }}>
      <h1 style={{ color: 'var(--text-primary)', fontSize: 22, fontWeight: 700, margin: '0 0 24px' }}>
        Settings
      </h1>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

        {/* Email reports */}
        <div style={cardStyle}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <div style={{ color: 'var(--text-primary)', fontSize: 14, fontWeight: 500 }}>
                Email reports
              </div>

              {hasRealEmail ? (
                <div style={{ color: 'var(--text-faint)', fontSize: 12, marginTop: 2 }}>
                  Send HTML report to{' '}
                  <span style={{ color: 'var(--brand)' }}>{user?.email}</span> after each analysis
                </div>
              ) : (
                // Warning shown when account has no real email (GitHub login with no public email)
                <div style={{ marginTop: 6 }}>
                  <div style={{
                    display: 'flex', alignItems: 'flex-start', gap: 8,
                    padding: '10px 12px', borderRadius: 8,
                    background: 'rgba(245,158,11,0.08)',
                    border: '1px solid rgba(245,158,11,0.25)',
                  }}>
                    <span style={{ color: 'var(--amber)', fontSize: 14, flexShrink: 0, marginTop: 1 }}>⚠</span>
                    <div>
                      <div style={{ color: 'var(--amber)', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                        No verified email address
                      </div>
                      <div style={{ color: 'var(--text-faint)', fontSize: 11, lineHeight: 1.5 }}>
                        Your GitHub account has no public email set, so email reports are disabled.
                        To enable them, either:
                      </div>
                      <ul style={{ color: 'var(--text-faint)', fontSize: 11, lineHeight: 1.7, margin: '6px 0 0 0', paddingLeft: 16 }}>
                        <li>
                          <strong style={{ color: 'var(--text-secondary)' }}>Sign in with Google</strong> —
                          log out and use <em>Continue with Google</em> with your Gmail account.
                          Your accounts will be merged automatically.
                        </li>
                        <li>
                          <strong style={{ color: 'var(--text-secondary)' }}>Set a public email on GitHub</strong> —
                          go to{' '}
                          <a
                            href="https://github.com/settings/profile"
                            target="_blank"
                            rel="noreferrer"
                            style={{ color: 'var(--brand)' }}
                          >
                            github.com/settings/profile
                          </a>
                          , add a public email, then log out and back in.
                        </li>
                      </ul>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <Toggle
              value={hasRealEmail ? emailReports : false}
              onChange={setEmailReports}
              disabled={!hasRealEmail}
            />
          </div>
        </div>

        {/* Risk threshold */}
        <div style={cardStyle}>
          <div style={{ color: 'var(--text-primary)', fontSize: 14, fontWeight: 500, marginBottom: 4 }}>
            Risk threshold for alerts
          </div>
          <div style={{ color: 'var(--text-faint)', fontSize: 12, marginBottom: 12 }}>
            Only flag changes at or above this risk level
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {[
              { r: 'LOW',    c: 'var(--green)', bg: 'var(--green-bg)', border: 'var(--green-border)' },
              { r: 'MEDIUM', c: 'var(--amber)', bg: 'var(--amber-bg)', border: 'rgba(245,158,11,0.3)' },
              { r: 'HIGH',   c: 'var(--red)',   bg: 'var(--red-bg)',   border: 'var(--red-border)' },
            ].map(({ r, c, bg, border }) => (
              <button
                key={r}
                onClick={() => setRiskThreshold(r)}
                style={{
                  padding: '7px 16px', borderRadius: 7, cursor: 'pointer',
                  fontSize: 12, fontWeight: 600,
                  border: `1px solid ${riskThreshold === r ? border : 'var(--border)'}`,
                  background: riskThreshold === r ? bg : 'transparent',
                  color: riskThreshold === r ? c : 'var(--text-faint)',
                  transition: 'all 0.15s',
                }}
              >{r}</button>
            ))}
          </div>
        </div>

        {/* Theme */}
        <div style={cardStyle}>
          <div style={{ color: 'var(--text-primary)', fontSize: 14, fontWeight: 500, marginBottom: 4 }}>
            Appearance
          </div>
          <div style={{ color: 'var(--text-faint)', fontSize: 12, marginBottom: 12 }}>
            Choose your preferred colour scheme
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {[
              { t: 'dark',  label: '🌙 Dark' },
              { t: 'light', label: '☀️ Light' },
            ].map(({ t, label }) => (
              <button
                key={t}
                onClick={() => applyTheme(t)}
                style={{
                  padding: '7px 20px', borderRadius: 7, cursor: 'pointer',
                  fontSize: 12, fontWeight: 600,
                  border: `1px solid ${theme === t ? 'var(--brand)' : 'var(--border)'}`,
                  background: theme === t ? 'var(--brand-bg)' : 'transparent',
                  color: theme === t ? 'var(--brand-muted)' : 'var(--text-faint)',
                  transition: 'all 0.15s',
                }}
              >{label}</button>
            ))}
          </div>
          <div style={{ color: 'var(--text-faintest)', fontSize: 11, marginTop: 8 }}>
            Preview applies instantly. Click Save to persist.
          </div>
        </div>

        {/* Account */}
        <div style={{
          ...cardStyle,
          border: '1px solid var(--red-border)',
        }}>
          <div style={{
            color: 'var(--red)', fontSize: 12, fontWeight: 600,
            letterSpacing: '0.05em', marginBottom: 8,
          }}>
            ACCOUNT
          </div>
          <div style={{ color: 'var(--text-faint)', fontSize: 12, marginBottom: 8 }}>
            Analysis data is stored on our servers. Your API keys are never stored.
          </div>
          <div style={{ color: 'var(--text-faintest)', fontSize: 11 }}>
            To delete your account and all data, contact support.
          </div>
        </div>

        <button
          onClick={save}
          disabled={saving}
          className="nx-btn"
          style={{ alignSelf: 'flex-start', padding: '11px 24px', borderRadius: 9, fontSize: 13 }}
        >
          {saving ? 'Saving...' : 'Save settings'}
        </button>

      </div>
    </div>
  )
}