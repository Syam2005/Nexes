import { useState } from 'react'
import { useAuth } from '../store/auth'
import api from '../utils/api'
import toast from 'react-hot-toast'

export default function ProfilePage() {
  const { user, refreshUser } = useAuth()
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'

  const [phone, setPhone] = useState(user?.phone || '')
  const [saving, setSaving] = useState(false)
  const [disconnecting, setDisconnecting] = useState(null)

  const connections = user?.github_connections || []

  const saveProfile = async () => {
    setSaving(true)
    try {
      await api.patch('/me', { phone })
      await refreshUser()
      toast.success('Profile saved')
    } catch {
      toast.error('Save failed')
    } finally {
      setSaving(false)
    }
  }

  const connectGitHub = () => {
    // FIX: pass JWT token as query param so backend can identify the user
    // Backend /auth/github/connect validates it and encodes as state=connect:<token>
    // GitHub then returns to the ONE registered callback /auth/github/callback
    const token = localStorage.getItem('nexus_token') || ''
    window.location.href = `${apiUrl}/auth/github/connect?token=${encodeURIComponent(token)}`
  }

  const disconnect = async (connId) => {
    setDisconnecting(connId)
    try {
      // Correct endpoint: DELETE /auth/github/{connection_id}
      await api.delete(`/auth/github/${connId}`)
      await refreshUser()
      toast.success('GitHub account disconnected')
    } catch {
      toast.error('Disconnect failed')
    } finally {
      setDisconnecting(null)
    }
  }

  return (
    <div style={{ padding: '24px 32px', maxWidth: 620, margin: '0 auto' }}>
      <h1 style={{ color: 'var(--text-primary)', fontSize: 22, fontWeight: 700, margin: '0 0 24px' }}>
        Profile
      </h1>

      {/* Avatar + basic info */}
      <div className="nx-card" style={{ padding: 24, marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
          {user?.photo_url ? (
            <img src={user.photo_url} alt="" style={{
              width: 64, height: 64, borderRadius: '50%',
              border: '2px solid var(--border)',
            }} />
          ) : (
            <div style={{
              width: 64, height: 64, borderRadius: '50%',
              background: 'linear-gradient(135deg, #312e81, #1e1b4b)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#818cf8', fontSize: 24, fontWeight: 700,
            }}>
              {user?.name?.[0]?.toUpperCase()}
            </div>
          )}
          <div>
            <div style={{ color: 'var(--text-primary)', fontSize: 16, fontWeight: 700 }}>
              {user?.name}
            </div>
            <div style={{ color: 'var(--text-faint)', fontSize: 13, marginTop: 2 }}>
              {user?.email}
            </div>
            <div style={{ color: 'var(--text-faintest)', fontSize: 11, marginTop: 2 }}>
              Signed in with {user?.auth_provider === 'google' ? 'Google' : 'GitHub'}
            </div>
          </div>
        </div>

        {/* Phone */}
        <div style={{ marginBottom: 16 }}>
          <label style={{
            color: 'var(--text-muted)', fontSize: 11, fontWeight: 600,
            letterSpacing: '0.05em', display: 'block', marginBottom: 6,
          }}>
            PHONE (optional)
          </label>
          <input
            className="nx-input"
            value={phone}
            onChange={e => setPhone(e.target.value)}
            placeholder="+1 234 567 8900"
          />
        </div>

        <button
          onClick={saveProfile}
          disabled={saving}
          style={{
            padding: '9px 20px', borderRadius: 8,
            background: 'var(--brand-bg)', border: '1px solid var(--brand)',
            color: 'var(--brand-muted)', fontSize: 13, fontWeight: 600, cursor: 'pointer',
          }}
        >
          {saving ? 'Saving...' : 'Save changes'}
        </button>
      </div>

      {/* GitHub connections */}
      <div className="nx-card" style={{ padding: 24 }}>
        <div style={{
          display: 'flex', alignItems: 'center',
          justifyContent: 'space-between', marginBottom: 16,
        }}>
          <div style={{
            color: 'var(--text-secondary)', fontSize: 12,
            fontWeight: 600, letterSpacing: '0.05em',
          }}>
            CONNECTED GITHUB ACCOUNTS
          </div>
          <button
            onClick={connectGitHub}
            style={{
              padding: '6px 14px', borderRadius: 7,
              border: '1px solid var(--border-muted)',
              background: '#161b22', color: '#e2e8f0',
              fontSize: 12, fontWeight: 500, cursor: 'pointer',
            }}
          >
            + Connect account
          </button>
        </div>

        {connections.length === 0 ? (
          <div style={{ color: 'var(--text-faint)', fontSize: 13, padding: '12px 0' }}>
            No GitHub accounts connected. Connect one to analyse private repos and commit changes.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {connections.map(c => (
              <div key={c.id} style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '10px 12px', borderRadius: 8,
                background: 'var(--bg-elevated)', border: '1px solid var(--border)',
              }}>
                {c.avatar_url ? (
                  <img src={c.avatar_url} alt="" style={{ width: 28, height: 28, borderRadius: '50%' }} />
                ) : (
                  <div style={{
                    width: 28, height: 28, borderRadius: '50%',
                    background: 'var(--border)', display: 'flex',
                    alignItems: 'center', justifyContent: 'center',
                    color: 'var(--text-faint)', fontSize: 12,
                  }}>GH</div>
                )}
                <div style={{ flex: 1 }}>
                  <div style={{ color: 'var(--text-primary)', fontSize: 13, fontWeight: 500 }}>
                    {c.github_username}
                  </div>
                  <div style={{ color: 'var(--text-faint)', fontSize: 11 }}>
                    Connected {new Date(c.connected_at).toLocaleDateString()}
                    {c.is_primary && (
                      <span style={{ marginLeft: 6, color: 'var(--brand)', fontWeight: 600 }}>
                        Primary
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => disconnect(c.id)}
                  disabled={disconnecting === c.id}
                  style={{
                    padding: '5px 12px', borderRadius: 6,
                    border: '1px solid var(--border-muted)',
                    background: 'transparent', color: 'var(--red)',
                    fontSize: 11, cursor: 'pointer',
                  }}
                >
                  {disconnecting === c.id ? '...' : 'Disconnect'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}